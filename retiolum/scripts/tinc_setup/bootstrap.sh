if [ ! `id -u` -eq "0" ] 
then
  echo "not root, trying sudo"
  exec sudo "$0" "$@"
fi

mkdir -p /etc/tinc/retiolum/
git clone git://github.com/miefda/retiolum.git /etc/tinc/retiolum/hosts
cd /etc/tinc/retiolum/hosts/.scripts

echo "use the build script of your choice from /etc/tinc/retiolum/hosts/.scripts"
