import distutils
import os
import py2exe
import re
import shutil
import sys

# Delete artifacts
try:
	os.system("del recite-*.zip")
	shutil.rmtree("build")
	shutil.rmtree("dist")
except:
	pass

# Get revision info from SVN
pipe = os.popen("svn info recite.py", "r")
out = pipe.read()
revision = re.findall("Revision: (\d+)", out, re.M)
if not len(revision):
	print "Recite revision not found: 'svn info recite.py'"
	print out
	sys.exit()
revision = "%06d" % int(revision[0])

# Build EXE
sys.argv.append('py2exe')
distutils.core.setup(console=["recite.py"], zipfile=None, options = {
	'py2exe': {
		'bundle_files': 1,
		'optimize': 2,
		'compressed': True,
		'excludes': [
			'_ssl',
			'win32api',
			'win32evtlog',
			'_hashlib',
			'select'
		]
	}
})

# Compress and package
os.system("upx --best dist\\recite.exe")
os.system("zip recite-%s.zip recite.py README.txt LICENSE.txt RECITE.pptx dist\\recite.exe" % revision)