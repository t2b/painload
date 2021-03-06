#! /usr/bin/env python
#
# //Reaktor/IRC/asybot.py
#

def is_executable(x):
  import os
  return os.path.exists(x) and os.access(x, os.X_OK)

from asynchat import async_chat as asychat
from asyncore import loop
from socket import AF_INET, SOCK_STREAM
from signal import SIGALRM, signal, alarm
from datetime import datetime as date, timedelta
from sys import exit
from re import split, search

import logging,logging.handlers
log = logging.getLogger('asybot')
hdlr = logging.handlers.SysLogHandler(facility=logging.handlers.SysLogHandler.LOG_DAEMON)
formatter = logging.Formatter( '%(filename)s: %(levelname)s: %(message)s')
hdlr.setFormatter(formatter)
log.addHandler(hdlr)

class asybot(asychat):
  def __init__(self, server, port, nickname, targets, **kwargs):
    asychat.__init__(self)
    self.server = server
    self.port = port
    self.nickname = nickname
    self.targets = targets
    self.username = kwargs['username'] if 'username' in kwargs else nickname
    self.hostname = kwargs['hostname'] if 'hostname' in kwargs else nickname
    self.ircname = kwargs['ircname'] if 'ircname' in kwargs else nickname
    self.realname = kwargs['realname'] if 'realname' in kwargs else nickname
    self.data = ''
    self.set_terminator('\r\n')
    self.create_socket(AF_INET, SOCK_STREAM)
    self.connect((self.server, self.port))

    # When we don't receive data for alarm_timeout seconds then issue a
    # PING every hammer_interval seconds until kill_timeout seconds have
    # passed without a message.  Any incoming message will reset alarm.
    self.alarm_timeout = 300
    self.hammer_interval = 10
    self.kill_timeout = 360
    signal(SIGALRM, lambda signum, frame: self.alarm_handler())
    self.reset_alarm()


  def reset_alarm(self):
    self.last_activity = date.now()
    alarm(self.alarm_timeout)

  def alarm_handler(self):
    delta = date.now() - self.last_activity
    if delta > timedelta(seconds=self.kill_timeout):
      log.error('No data for %s.  Giving up...' % delta)
      exit(2)
    else:
      log.error('No data for %s.  PINGing server...' % delta)
      self.push('PING :%s' % self.nickname)
      alarm(self.hammer_interval)

  def collect_incoming_data(self, data):
    self.data += data

  def found_terminator(self):
    log.debug('<< %s' % self.data)

    message = self.data
    self.data = ''

    _, prefix, command, params, rest, _ = \
        split('^(?::(\S+)\s)?(\S+)((?:\s[^:]\S*)*)(?:\s:(.*))?$', message)
    params = params.split(' ')[1:]
    #print([prefix, command, params, rest])

    if command == 'PING':
      self.push('PONG :%s' % rest)
      log.info("Replying to servers PING with PONG :%s" %rest)

    elif command == 'PRIVMSG':
      self.on_privmsg(prefix, command, params, rest)

    elif command == '433':
      # ERR_NICKNAMEINUSE, retry with another name
      _, nickname, int, _ = split('^.*[^0-9]([0-9]+)$', self.nickname) \
          if search('[0-9]$', self.nickname) \
          else ['', self.nickname, 0, '']
      self.nickname = nickname + str(int + 1)
      self.handle_connect()

    self.reset_alarm()

  def push(self, message):
    log.debug('>> %s' % message)
    asychat.push(self, message + self.get_terminator())

  def handle_connect(self):
    self.push('NICK %s' % self.nickname)
    self.push('USER %s %s %s :%s' %
        (self.username, self.hostname, self.server, self.realname))
    self.push('JOIN %s' % ','.join(self.targets))

  def on_privmsg(self, prefix, command, params, rest):
    def PRIVMSG(text):
      msg = 'PRIVMSG %s :%s' % (','.join(params), text)
      self.push(msg)

    def ME(text):
      PRIVMSG('ACTION ' + text + '')

    _from = prefix.split('!', 1)[0]

    try:
      _, _handle, _command, _argument, _ = split(
          '^(\w+|\*):\s*(\w+)(?:\s+(.*))?$', rest)
    except ValueError, error:
      if search(self.nickname, rest):
        PRIVMSG('I\'m so famous')
      return # ignore

    if _handle == self.nickname or _handle == '*':

      from os.path import realpath, dirname, join
      from subprocess import Popen as popen, PIPE

      Reaktor_dir = dirname(realpath(dirname(__file__)))
      public_commands = join(Reaktor_dir, 'public_commands')
      command = join(public_commands, _command)

      if is_executable(command):

        env = {}
        if _argument != None:
          env['argument'] = _argument

        try:
          p = popen([command], stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env)
        except OSError, error:
          ME('brain damaged')
          log.error('OSError@%s: %s' % (command, error))
          return

        stdout, stderr = [ x[:len(x)-1] for x in
            [ x.split('\n') for x in p.communicate()]]
        code = p.returncode
        pid = p.pid

        log.info('command: %s -> %s' % (command, code))
        [log.debug('%s stdout: %s' % (pid, x)) for x in stdout]
        [log.debug('%s stderr: %s' % (pid, x)) for x in stderr]

        if code == 0:
          [PRIVMSG(x) for x in stdout]
          [PRIVMSG(x) for x in stderr]
        else:
          ME('mimimi')

      else:
        if _handle != '*':
          PRIVMSG(_from + ': you are made of stupid')


# retrieve the value of a [singleton] variable from a tinc.conf(5)-like file
def getconf1(x, path):
  from re import findall
  pattern = '(?:^|\n)\s*' + x + '\s*=\s*(.*\w)\s*(?:\n|$)'
  y = findall(pattern, open(path, 'r').read())
  if len(y) < 1:
    raise AttributeError("len(getconf1('%s', '%s') < 1)" % (x, path))
  if len(y) > 1:
    y = ' '.join(y)
    raise AttributeError("len(getconf1('%s', '%s') > 1)\n  ====>  %s"
        % (x, path, y))
  return y[0]

if __name__ == "__main__":
  from os import environ as env

  lol = logging.DEBUG if env.get('debug',False) else logging.INFO
  logging.basicConfig(level=lol)
  name = getconf1('Name', '/etc/tinc/retiolum/tinc.conf')
  hostname = '%s.retiolum' % name
  nick = str(env.get('nick', name))
  host = str(env.get('host', 'supernode'))
  port = int(env.get('port', 6667))
  target = str(env.get('target', '#retiolum'))
  log.info('=> irc://%s@%s:%s/%s' % (nick, host, port, target))

  from getpass import getuser
  asybot(host, port, nick, [target], username=getuser(),
      ircname='//Reaktor running at %s' % hostname,
      hostname=hostname)

  loop()
