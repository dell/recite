#######################################################################
# Copyright (c) 2012, Dell Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#	 * Redistributions of source code must retain the above copyright
#	   notice, this list of conditions, and the following disclaimer.
#	 * Redistributions in binary form must reproduce the above copyright
#	   notice, this list of conditions and the following disclaimer in the
#	   documentation and/or other materials provided with the distribution:
#	 * Neither the name of the Dell Inc. nor the names of its contributors
#	   may be used to endorse or promote products derived from this
#	   software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL Dell Inc. BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
#######################################################################

import ConfigParser
import StringIO
import atexit
import getpass
import glob
import os
import os.path
import pickle
import re
import shlex
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import types
import xml.dom.minidom

try:
	import readline
except:
	pass

# Defaults
LOGINDEFAULT = "root"
PASSDEFAULT = "calvin"
PORTDEFAULT = 443

# Strings
NAME = "name"
COMMAND = "command"
URL = "url"
PARAMS = "params"
GETPARAMS = "getparams"
DEFAULT = "default"
EXAMPLE = "example"
NORMAL = "normal"
XML = "xml"
PRETTY = "prettyxml"
GLOBAL = "global"

# WS-MAN address contruction
ADDRESSREF = """  <p:%s xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing" xmlns:w="http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd">
	<a:Address>http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</a:Address>
	<a:ReferenceParameters>
	  <w:ResourceURI>%s</w:ResourceURI>
	  <w:SelectorSet>
%s
	  </w:SelectorSet>
	</a:ReferenceParameters>
  </p:%s>
"""

SELECTORREF = '        <w:Selector Name="%s">%s</w:Selector>'

# XML object generation
OBJECT = '<obj type="%s" name="%s">%s</obj>'

# Internal variables
VAR_BATCHFILE = "$_BATCHFILE"
VAR_DATE = "$_DATE"
VAR_LOCALIP = "$_LOCALIP"
VAR_LINE = "$_LINE"

# Private variables
VAR_UNTIL = "$_UNTIL"
VAR_FIND = "$_FIND"
VAR_PARENT = "$_PARENT"
VAR_COUNT = "$_COUNT"

# Settable variables
FORMAT = "$FORMAT"
IP = "$IP"
LOGIN = "$LOGIN"
PASS = "$PASS"
PORT = "$PORT"
PROGRAM = "$PROGRAM"
TIMER = "$TIMER"
USLEEP = "$USLEEP"
UTIMEOUT = "$UTIMEOUT"
VERBOSE = "$VERBOSE"

# Verbosity levels
VERBOSE_QUIET = 0
VERBOSE_WSMAN = 1
VERBOSE_FULL = 2

# Required variables
REQ_VARIABLES = [
	FORMAT,
	IP,
	LOGIN,
	PASS,
	PORT,
	PROGRAM,
	TIMER,
	USLEEP,
	UTIMEOUT,
	VERBOSE
]

# PyRecite commands
PYRECITE = [
	"batch",
	"context",
	"count",
	"find",
	"findall",
	"set",
	"sleep",
	"unset",
	"until"
]

# Meta methods
METAMETHODS = [
	"GetEPR",
	"GetClass",
	"GetInstance"
]

# Global data
BATCH = []
CACHED_EPR = {}
CONTEXT = None
GOTO = None
INPUT = ""
INPUTXML = ""
LOGFILE = None
LOGGER = None
OUTPUT = ""
OUTPUTXML = ""
OUTPUTXMLOBJ = None
RETURN = []
TEMPFILES = []
try:
	LOCALIP = socket.gethostbyname(socket.gethostname())
except:
	LOCALIP = ""
	print "Unable to detect LOCALIP"

try:
	VERBOSE_INIT = int(os.getenv("VERBOSE"))
except:
	VERBOSE_INIT = VERBOSE_FULL

# Global variables
VARIABLES = {
	FORMAT: NORMAL,
	IP: "",
	LOGIN: os.getenv("LOGIN") or LOGINDEFAULT,
	PASS: os.getenv("PASS") or PASSDEFAULT,
	PORT: PORTDEFAULT,
	PROGRAM: "False",
	TIMER: os.getenv("TIMER") or "False",
	USLEEP: os.getenv("USLEEP") or "30",
	UTIMEOUT: os.getenv("UTIMEOUT") or "900",
	VERBOSE: VERBOSE_INIT,

	VAR_LOCALIP: LOCALIP,
}

# Internal methods
INTERNAL = {
	"Batch": [
		"Execute a list of commands from specified file",
		"  Batch Filename.win",
		"  Filename.win",
		"",
		"  Batch C:\\Path\\Filename.win",
		"  C:\\Path\\Filename.win",
		"Start execution at specified line from specified file",
		"  Batch multiline.win:10",
		"Start execution at specified label from specified file",
		"  Batch multiline.win:StartLabel",
	],

	"Clear": [
		"Clear the screen",
		"  Clear"
	],

	"Context": [
		"Perform a find/findall in specified context since some methods return multiple chunks.",
		"Context can filter down to single chunk on which find/findall should be performed",
		"  Context Name=Value Find ...",
		"  Context Name=Value Findall ...",
		"  //Name=Value ...",
		"Get CurrentValue of NicMode",
		"  Context AttributeName=NicMode Find CurrentValue $cid",
		"  //AttributeName=NicMode Find CurrentValue $cid",
		"  //AttributeName=NicMode /$cid=CurrentValue",
		"Get all PossibleValues of NicMode",
		"  Context AttributeName=NicMode Findall PossibleValues $pvals",
		"  //AttributeName=NicMode Findall PossibleValues $pvals",
		"  //AttributeName=NicMode /*$pvals=PossibleValues",
		"Check if CurrentValue of NicMode=Enabled",
		"  Context AttributeName=NicMode Find CurrentValue=Enabled",
		"  //AttributeName=NicMode Find CurrentValue=Enabled",
		"  //AttributeName=NicMode /CurrentValue=Enabled"
	],

	"Count": [
		"Some methods return multiple chunks. Count the total number of chunks",
		"  Count $var",
		"  +$var"
	],

	"Exit": [
		"Exit Recite from interactive mode"
	],

	"Find": [
		"Find specified string in output from preceding command",
		"  Find Name[=Value] [$var] [1-9]",
		"  /Name=Value",
		"  /$var=Name",
		"Check if Name=Value",
		"  Find Name=Value",
		"  /Name=Value",
		"  Find Status=Ready",
		"  /Status=Ready",
		"Check if Name=Value, save found value in $var",
		"  Find Name=Value $var",
		"Check if 2nd Name=Value, save found value in $var",
		"  Find Name=Value $var 2",
		"Save found value in $ctlr",
		"  Find InstanceID $ctlr",
		"  /$ctlr=InstanceID",
		"Save 2nd found value in $jid",
		"  Find InstanceID $jid 2"
	],

	"Findall": [
		"Find all instances of specified string in output from preceding command",
		"  Findall Name $var",
		"  /*$var=Name",
	],

	"Gosub": [
		"Goto specified line as a sub-routine, enables Return from sub-routine",
		"  Gosub 10",
		"  >>10",
		"Goto specified line in an external sript as a sub-routine",
		"  Gosub otherscript.win:10",
		"  >>otherscript.win:10",
		"Goto specified label as a subroutine",
		"  Gosub Routine",
		"  >>Routine",
		"Goto specified label in an external script as a subroutine",
		"  Gosub script.win:Routine",
		"  >>script.win:Routine",
		"Labels can be defined using :Label",
		"  :End"
	],

	"Goto": [
		"Goto specified line",
		"  Goto 10",
		"  >10",
		"Goto specified line in an external script - does not return",
		"  Goto otherscript.win:10",
		"  >otherscript.win:10",
		"Goto specified label",
		"  Goto End",
		"  >End",
		"Goto specified label in an external script - does not return",
		"  Goto script.win:End",
		"  >script.win:End",
		"Labels can be defined using :Label",
		"  :End"
	],

	"Help": [
		"Display help menu of all available methods",
		"  help",
		"Display help for specific method",
		"  help CreateVirtualDisk"
	],

	"If": [
		"If Name=Value execute specified command",
		"  If Name=Value Command",
		"  ?Name=Value Command",
		"  If $ctlr=RAID.Integrated.1-1 Goto 10",
		"  ?$ctlr=RAID.Integrated.1-1 >10",
		"  If $status=Ready GetLifecycleJob JobID=JID_001299001074"
	],

	"Log": [
		"Enable logging to specified file - overwrite by default",
		"  Log filename",
		"Specify mode for logging - overwrite or append",
		"  Log filename w",
		"  Log filename a",
		"Stop logging",
		"  Log"
	],

	"Print": [
		"Print text substituting variables",
		"  Print Hello World",
		"  <Hello World",
		"  Print Login is $LOGIN",
		"  <Login is $LOGIN",
		"  Print Return Value = $ret",
		"  <Return Value = $ret"
	],

	"Quit": [
		"Quit Recite from interactive mode"
	],

	"Report": [
		"Generate report from output of preceding command",
		"  Report Field1,Field2,Field3",
		"  <<Field1,Field2,Field3",
		"  Report Field1,Field2 where Field3=String",
		"  <<Field1,Field2 //Field3=String",
		"Report is sorted by order of fields specified"
		"  Report Field1,*",
		"  <<Field1,*",
		"  Report Field1,* where Field2=String",
		"  <<Field1,* //Field2=String",
		"Sort by first field found",
		"  Report *",
		"  <<*",
		"  Report * where Field2=String",
		"  <<* //Field2=String"
	],

	"Return": [
		"Return from a sub-routine",
		"Returns to the last Gosub",
		"  Return"
	],

	"Set": [
		"Show list of set variables",
		"  Set",
		"  $",
		"Set variable to value",
		"  Set $var Value",
		"  $var=Value",
		"  Set $bios BIOS.Setup.1-1",
		"  $bios=BIOS.Setup.1-1",
		"  Set $inst $bios:EmbNic1",
		"  $inst=$bios:EmbNic1",
		"Set variable to expression",
		"  Set /a $var $var+1",
		"  $var:=$var+1",
		"  Set /a $counter $counter*5",
		"  $counter:=$counter*5"
	],

	"Sleep": [
		"Sleep for specified amount of seconds",
		"  Sleep 5"
	],

	"Unset": [
		"Unset specified variable",
		"  Unset $var",
		"  ~$var",
		"  Unset $ctlr",
		"  ~$ctlr"
	],

	"Until": [
		"Run specified method every X seconds, total Y seconds until Name=Value",
		"  Until Name=Value [X Y] Method Params...",
		"  {Name=Value [X Y] Method Params...",
		"If omitted, X and Y are replaced with $USLEEP and $UTIMEOUT which are user changeable",
		"Check DM status every 10 seconds for 10 mins total until Status=Ready",
		"  Until Status=Ready 10 600 GetRSStatus",
		"  {Status=Ready 10 600 GetRSStatus",
		"  {Status=Ready GetRSStatus"
	],
}

BIOS_METHODS = {
	"ChangePassword": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_BIOSService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_BIOSService+SystemName=DCIM:ComputerSystem+Name=DCIM:BIOSService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "BIOS.Setup.1-1"
			},
			"PasswordType": {
				DEFAULT: None,
				EXAMPLE: "1=System, 2=Setup"
			},
			"OldPassword": {
				DEFAULT: "",
				EXAMPLE: "OLDPASSWORD"
			},
			"NewPassword": {
				DEFAULT: "",
				EXAMPLE: "NEWPASSWORD"
			}
		}
	},

	"CreateBIOSConfigJob": {
		NAME: "CreateTargetedConfigJob",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_BIOSService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_BIOSService+SystemName=DCIM:ComputerSystem+Name=DCIM:BIOSService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "BIOS.Setup.1-1"
			},
			"RebootJobType": {
				DEFAULT: "",
				EXAMPLE: "3"
			},
			"ScheduledStartTime": {
				DEFAULT: "",
				EXAMPLE: "TIME_NOW"
			},
			"UntilTime": {
				DEFAULT: "",
				EXAMPLE: 20211111111111
			}
		}
	},

	"DeletePendingBIOSConfiguration": {
		NAME: "DeletePendingConfiguration",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_BIOSService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_BIOSService+SystemName=DCIM:ComputerSystem+Name=DCIM:BIOSService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "BIOS.Setup.1-1"
			}
		}
	},

	"GetBIOSEnumeration": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_BIOSEnumeration",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "BIOS.Setup.1-1:NumLock"
			}
		}
	},

	"GetBIOSEnumerations": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_BIOSEnumeration"
	},

	"GetBIOSInteger": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_BIOSInteger",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "BIOS.Slot.1-1:AcPwrRcvryUserDelay"
			}
		}
	},

	"GetBIOSIntegers": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_BIOSInteger"
	},

	"GetBIOSString": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_BIOSString",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "BIOS.Slot.1-1:OneTimeCustomBootStr"
			}
		}
	},

	"GetBIOSStrings": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_BIOSString"
	},

	"SetBIOSAttribute": {
		NAME: "SetAttribute",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_BIOSService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_BIOSService+SystemName=DCIM:ComputerSystem+Name=DCIM:BIOSService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "BIOS.Slot.1-1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: "IpVer"
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: "IPv4"
			}
		}
	},

	"SetBIOSAttributes": {
		NAME: "SetAttributes",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_BIOSService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_BIOSService+SystemName=DCIM:ComputerSystem+Name=DCIM:BIOSService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "BIOS.Slot.1-1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: ["IpVer", "WakeOnLan"]
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: ["IPv4", "Disabled"]
			}
		}
	}
}

FC_METHODS = {
	"CreateFCConfigJob": {
		NAME: "CreateTargetedConfigJob",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_FCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_FCService+SystemName=DCIM:ComputerSystem+Name=DCIM:FCService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "FC.Slot.1-1"
			},
			"RebootJobType": {
				DEFAULT: "",
				EXAMPLE: "3"
			},
			"ScheduledStartTime": {
				DEFAULT: "",
				EXAMPLE: "TIME_NOW"
			},
			"UntilTime": {
				DEFAULT: "",
				EXAMPLE: 20211111111111
			}
		}
	},

	"DeletePendingFCConfiguration": {
		NAME: "DeletePendingConfiguration",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_FCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_FCService+SystemName=DCIM:ComputerSystem+Name=DCIM:FCService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "FC.Slot.1-1"
			}
		}
	},

	"GetFCAttributes": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_FCAttribute"
	},

	"GetFCEnumeration": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_FCEnumeration",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "FC.Slot.1-1:BootScanSelection"
			}
		}
	},

	"GetFCEnumerations": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_FCEnumeration"
	},

	"GetFCCapability": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_FCCapabilities",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "FC.Slot.1-1"
			}
		}
	},

	"GetFCCapabilities": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_FCCapabilities"
	},

	"GetFCInteger": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_FCInteger",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "FC.Slot.1-1:FirstFCTargetLUN"
			}
		}
	},

	"GetFCIntegers": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_FCInteger"
	},

	"GetFCStatistic": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_FCStatistics",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "FC.Slot.1-1"
			}
		}
	},

	"GetFCStatistics": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_FCStatistics"
	},

	"GetFCString": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_FCString",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "FC.Slot.1-1:WWN"
			}
		}
	},

	"GetFCStrings": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_FCString"
	},

	"GetFCView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_FCView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "FC.Slot.1-1"
			}
		}
	},

	"GetFCViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_FCView"
	},

	"SetFCAttribute": {
		NAME: "SetAttribute",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_FCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_FCService+SystemName=DCIM:ComputerSystem+Name=DCIM:FCService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "FC.Slot.1-1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: "PortDownRetryCount"
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: "30"
			}
		}
	},

	"SetFCAttributes": {
		NAME: "SetAttributes",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_FCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_FCService+SystemName=DCIM:ComputerSystem+Name=DCIM:FCService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "FC.Slot.1-1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: ["PortDownRetryCount", "BootScanSelection"]
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: ["30", "Disabled"]
			}
		}
	}
}

NIC_METHODS = {
	"CreateNICConfigJob": {
		NAME: "CreateTargetedConfigJob",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_NICService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_NICService+SystemName=DCIM:ComputerSystem+Name=DCIM:NICService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "NIC.Slot.1-1"
			},
			"RebootJobType": {
				DEFAULT: "",
				EXAMPLE: "3"
			},
			"ScheduledStartTime": {
				DEFAULT: "",
				EXAMPLE: "TIME_NOW"
			},
			"UntilTime": {
				DEFAULT: "",
				EXAMPLE: 20211111111111
			}
		}
	},

	"DeletePendingNICConfiguration": {
		NAME: "DeletePendingConfiguration",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_NICService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_NICService+SystemName=DCIM:ComputerSystem+Name=DCIM:NICService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "NIC.Slot.1-1"
			}
		}
	},

	"GetNICAttributes": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_NICAttribute"
	},

	"GetNICEnumeration": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_NICEnumeration",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "NIC.Slot.1-1:IpVer"
			}
		}
	},

	"GetNICEnumerations": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_NICEnumeration"
	},

	"GetNICCapability": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_NICCapabilities",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "NIC.Slot.1-1"
			}
		}
	},

	"GetNICCapabilities": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_NICCapabilities"
	},

	"GetNICInteger": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_NICInteger",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "NIC.Slot.1-1:VLanId"
			}
		}
	},

	"GetNICIntegers": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_NICInteger"
	},

	"GetNICStatistic": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_NICStatistics",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "NIC.Slot.1-1"
			}
		}
	},

	"GetNICStatistics": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_NICStatistics"
	},

	"GetNICString": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_NICString",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "NIC.Slot.1-1:VirtMacAddr"
			}
		}
	},

	"GetNICStrings": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_NICString"
	},

	"GetNICView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_NICView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "NIC.Slot.1-1"
			}
		}
	},

	"GetNICViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_NICView"
	},

	"SetNICAttribute": {
		NAME: "SetAttribute",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_NICService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_NICService+SystemName=DCIM:ComputerSystem+Name=DCIM:NICService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "NIC.Slot.1-1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: "IpVer"
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: "IPv4"
			}
		}
	},

	"SetNICAttributes": {
		NAME: "SetAttributes",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_NICService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_NICService+SystemName=DCIM:ComputerSystem+Name=DCIM:NICService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "NIC.Slot.1-1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: ["IpVer", "WakeOnLan"]
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: ["IPv4", "Disabled"]
			}
		}
	}
}

RAID_METHODS = {
	"AssignSpare": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "Disk.Bay.0:Enclosure.Internal.0-0:RAID.Integrated.1-1"
			},
			"VirtualDiskArray": {
				DEFAULT: "",
				EXAMPLE: "Disk.Virtual.0:RAID.Integrated.1-1"
			}
		}
	},

	"CheckVDValues": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			},
			"PDArray": {
				DEFAULT: None,
				EXAMPLE: "Disk.Bay.0:Enclosure.Internal.0-0:RAID.Integrated.1-1"
			},
			"VDPropNameArrayIn": {
				DEFAULT: ["RAIDLevel"],
				EXAMPLE: ["RAIDLevel", "SpanDepth", "Size", "StartingLBA"]
			},
			"VDPropValueArrayIn": {
				DEFAULT: None,
				EXAMPLE: ["2", "1", "..."]
			}
		}
	},

	"ClearForeignConfig": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			}
		}
	},

	"ConvertToRAID": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"PDArray": {
				DEFAULT: None,
				EXAMPLE: "Disk.Bay.0:Enclosure.Internal.0-0:RAID.Integrated.1-1"
			},
		}
	},

	"ConvertToNonRAID": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"PDArray": {
				DEFAULT: None,
				EXAMPLE: "Disk.Bay.0:Enclosure.Internal.0-0:RAID.Integrated.1-1"
			},
		}
	},

	"CreateRAIDConfigJob": {
		NAME: "CreateTargetedConfigJob",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			},
			"RebootJobType": {
				DEFAULT: "",
				EXAMPLE: "3"
			},
			"ScheduledStartTime": {
				DEFAULT: "",
				EXAMPLE: "TIME_NOW"
			},
			"UntilTime": {
				DEFAULT: "",
				EXAMPLE: 20211111111111
			}
		}
	},

	"CreateVirtualDisk": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			},
			"PDArray": {
				DEFAULT: None,
				EXAMPLE: "Disk.Bay.0:Enclosure.Internal.0-0:RAID.Integrated.1-1"
			},
			"VDPropNameArray": {
				DEFAULT: ["RAIDLevel", "SpanLength"],
				EXAMPLE: ["RAIDLevel", "SpanLength", "SpanDepth", "Size", "VirtualDiskName", "StripeSize", "ReadPolicy", "WritePolicy", "DiskCachePolicy", "Initialize", "StartingLBA", "Cachecade"]
			},
			"VDPropValueArray": {
				DEFAULT: None,
				EXAMPLE: ["2", "1", "..."]
			}
		}
	},

	"DeletePendingRAIDConfiguration": {
		NAME: "DeletePendingConfiguration",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID:Integrated:1-1"
			}
		}
	},

	"DeleteVirtualDisk": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "Disk.Virtual.0:RAID.Integrated.1-1"
			}
		}
	},

	"EnableControllerEncryption": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			},
			"Mode": {
				DEFAULT: None,
				EXAMPLE: "1"
			},
			"Key": {
				DEFAULT: None,
				EXAMPLE: "SECRET"
			},
			"Keyid": {
				DEFAULT: None,
				EXAMPLE: "MyFavoriteKey"
			}
		}
	},

	"GetAvailableDisks": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			},
			"RaidLevel": {
				DEFAULT: "",
				EXAMPLE: 2
			},
			"DiskType": {
				DEFAULT: 0
			},
			"Diskprotocol": {
				DEFAULT: 0
			},
			"DiskEncrypt": {
				DEFAULT: 0
			}
		}
	},

	"GetControllerView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_ControllerView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			}
		}
	},

	"GetControllerViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_ControllerView"
	},

	"GetDHSDisks": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "Disk.Virtual.0:RAID.Integrated.1-1"
			}
		}
	},

	"GetEnclosureView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_EnclosureView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "Enclosure.Internal.0-0:RAID.Integrated.1-1"
			}
		}
	},

	"GetEnclosureViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_EnclosureView"
	},

	"GetPhysicalDiskView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_PhysicalDiskView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "Disk.Bay.0:Enclosure.Internal.0-0:RAID.Integrated.1-1"
			}
		}
	},

	"GetPhysicalDiskViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_PhysicalDiskView"
	},

	"GetRAIDEnumeration": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_RAIDEnumeration",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "RAID.Slot.3-1:RAIDSupportedRAIDLevels"
			}
		}
	},

	"GetRAIDEnumerations": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_RAIDEnumeration"
	},

	"GetRAIDInteger": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_RAIDInteger",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1:RAIDrebuildRate"
			}
		}
	},

	"GetRAIDIntegers": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_RAIDInteger"
	},

	"GetRAIDLevels": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			},
			"PDArray": {
				DEFAULT: "",
				EXAMPLE: ["Disk.Bay.0:Enclosure.Internal.0-0:RAID.Integrated.1-1"]
			},
			"DiskType": {
				DEFAULT: 0
			},
			"Diskprotocol": {
				DEFAULT: 0
			},
			"DiskEncrypt": {
				DEFAULT: 0
			}
		}
	},

	"GetRAIDString": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_RAIDString",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "Disk.Virtual.0:RAID.Integrated.1-1:Name"
			}
		}
	},

	"GetRAIDStrings": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_RAIDString"
	},

	"GetVirtualDiskView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_VirtualDiskView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "Disk.Virtual.0:RAID.Integrated.1-1"
			}
		}
	},

	"GetVirtualDiskViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_VirtualDiskView"
	},

	"LockVirtualDisk": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "Disk.Virtual.0:RAID.Integrated.1-1"
			}
		}
	},

	"ReKey": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			},
			"Mode": {
				DEFAULT: None,
				EXAMPLE: "1"
			},
			"OldKey": {
				DEFAULT: None,
				EXAMPLE: "SECRET"
			},
			"NewKey": {
				DEFAULT: None,
				EXAMPLE: "SECRET"
			},
			"Keyid": {
				DEFAULT: None,
				EXAMPLE: "MyFavoriteKey"
			}
		}
	},

	"RemoveControllerKey": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			}
		}
	},

	"ResetConfig": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			}
		}
	},

	"SetControllerKey": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			},
			"Key": {
				DEFAULT: None,
				EXAMPLE: "SECRET"
			},
			"Keyid": {
				DEFAULT: None,
				EXAMPLE: "MyFavoriteKey"
			}
		}
	},

	"SetRAIDAttribute": {
		NAME: "SetAttribute",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: "RAIDccMode"
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: "Normal"
			}
		}
	},

	"SetRAIDAttributes": {
		NAME: "SetAttributes",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "RAID.Integrated.1-1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: ["RAIDccMode", "RAIDprMode"]
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: ["Normal", "Disabled"]
			}
		}
	},

	"UnassignSpare": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_RAIDService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_RAIDService+SystemName=DCIM:ComputerSystem+Name=DCIM:RAIDService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "Disk.Bay.0:Enclosure.Internal.0-0:RAID.Integrated.1-1"
			},
		}
	}
}

iDRAC_METHODS = {
	"ApplyAttribute": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_iDRACCardService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_iDRACCardService+SystemName=DCIM:ComputerSystem+Name=DCIM:iDRACCardService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: "Users.4#Enable"
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: "Enabled"
			}
		}
	},

	"ApplyAttributes": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_iDRACCardService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_iDRACCardService+SystemName=DCIM:ComputerSystem+Name=DCIM:iDRACCardService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: ["Users.4#Enable", "Users.5#Enable"]
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: ["Enabled", "Disabled"]
			}
		}
	},

	"SetiDRACAttribute": {
		NAME: "SetAttribute",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_IDRACCardService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_iDRACCardService+SystemName=DCIM:ComputerSystem+Name=DCIM:iDRACCardService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: "Users.4#Enable"
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: "Enabled"
			}
		}
	},

	"SetiDRACAttributes": {
		NAME: "SetAttributes",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_IDRACCardService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_iDRACCardService+SystemName=DCIM:ComputerSystem+Name=DCIM:iDRACCardService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: ["Users.4#Enable", "Users.5#Enable"]
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: ["Enabled", "Disabled"]
			}
		}
	},

	"CreateiDRACConfigJob": {
		NAME: "CreateTargetedConfigJob",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_IDRACCardService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_iDRACCardService+SystemName=DCIM:ComputerSystem+Name=DCIM:iDRACCardService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "System.Embedded.1"
			},
			"RebootJobType": {
				DEFAULT: "",
				EXAMPLE: "3"
			},
			"ScheduledStartTime": {
				DEFAULT: "",
				EXAMPLE: "TIME_NOW"
			},
			"UntilTime": {
				DEFAULT: "",
				EXAMPLE: 20211111111111
			}
		}
	},

	"DeletePendingiDRACConfiguration": {
		NAME: "DeletePendingConfiguration",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_IDRACCardService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_iDRACCardService+SystemName=DCIM:ComputerSystem+Name=DCIM:iDRACCardService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "System.Embedded.1"
			}
		}
	},

	"GetiDRACCardAttributes": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_iDRACCardAttribute"
	},

	"GetiDRACCardEnumeration": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_iDRACCardEnumeration",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1#NIC.1#Enable"
			}
		}
	},

	"GetiDRACCardEnumerations": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_iDRACCardEnumeration"
	},

	"GetiDRACCardInteger": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_iDRACCardInteger",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1#Users.15#Privilege"
			}
		}
	},

	"GetiDRACCardIntegers": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_iDRACCardInteger"
	},

	"GetiDRACCardString": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_iDRACCardString",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1#Users.1#UserName"
			}
		}
	},

	"GetiDRACCardStrings": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_iDRACCardString"
	},

	"GetiDRACCardView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_iDRACCardView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1"
			}
		}
	},

	"GetiDRACCardViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_iDRACCardView"
	}
}

POWER_METHODS = {
	"GetPowerManagementCapabilities": {
		COMMAND: "enumerate",
		URL: "cimv2/CIM_PowerManagementCapabilities"
	},

	"RequestStateChange": {
		COMMAND: "invoke",
		URL: "EPR:CIM_ComputerSystem",
		PARAMS: {
			"RequestedState": {
				DEFAULT: None,
				EXAMPLE: 11
			}
		}
	},

	"RequestPowerStateChange": {
		COMMAND: "invoke",
		URL: "EPR:CIM_PowerManagementService",
		PARAMS: {
			"PowerState": {
				DEFAULT: None,
				EXAMPLE: 3
			},
			"ManagedElement": {
				DEFAULT: "EPR:CIM_ComputerSystem"
			}
		}
	}
}

JOB_METHODS = {
	"CreateRebootJob": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_SoftwareInstallationService?CreationClassName=DCIM_SoftwareInstallationService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=IDRAC:ID+Name=SoftwareUpdate",
		PARAMS: {
			"RebootJobType": {
				DEFAULT: None,
				EXAMPLE: "3"
			}
		}
	},

	"DeleteJobQueue": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_JobService?CreationClassName=DCIM_JobService+Name=JobService+SystemName=Idrac+SystemCreationClassName=DCIM_ComputerSystem",
		PARAMS: {
			"JobID": {
				DEFAULT: "JID_CLEARALL"
			}
		}
	},

	"GetLifecycleJob": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_LifecycleJob",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "JID_CLEARALL"
			}
		}
	},

	"GetLifecycleJobs": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_LifecycleJob"
	},

	"SetupJobQueue": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_JobService?CreationClassName=DCIM_JobService+Name=JobService+SystemName=Idrac+SystemCreationClassName=DCIM_ComputerSystem",
		PARAMS: {
			"JobArray": {
				DEFAULT: None,
				EXAMPLE: ["JID_001249463339", "RID_001265817718"]
			},
			"StartTimeInterval": {
				DEFAULT: "",
				EXAMPLE: "TIME_NOW"
			},
			"UntilTime": {
				DEFAULT: "",
				EXAMPLE: 20211111111111
			}
		}
	}
}

LC_METHODS = {
	"CreateLCConfigJob": {
		NAME: "CreateConfigJob",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService"
	},

	"ExportHWInventory": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService",
		PARAMS: {
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "10.0.0.1"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name"
			},
			"FileName": {
				DEFAULT: None,
				EXAMPLE: "lclog.xml"
			},
			"ShareType": {
				DEFAULT: "2",
				EXAMPLE: "0=NFS, 2=CIFS"
			},
			"Username": {
				DEFAULT: "",
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "password"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			}
		}
	},

	"ExportFactoryConfiguration": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService",
		PARAMS: {
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "10.0.0.1"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name"
			},
			"FileName": {
				DEFAULT: None,
				EXAMPLE: "lclog.xml"
			},
			"ShareType": {
				DEFAULT: "2",
				EXAMPLE: "0=NFS, 2=CIFS"
			},
			"Username": {
				DEFAULT: "",
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "password"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			}
		}
	},

	"ExportLCLog": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService",
		PARAMS: {
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "10.0.0.1"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name"
			},
			"FileName": {
				DEFAULT: None,
				EXAMPLE: "lclog.xml"
			},
			"ShareType": {
				DEFAULT: "2",
				EXAMPLE: "0=NFS, 2=CIFS"
			},
			"Username": {
				DEFAULT: "",
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "password"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			}
		}
	},

	"GetLCEnumeration": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_LCEnumeration",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "DCIM_LCEnumeration:CCR4"
			}
		}
	},

	"GetLCEnumerations": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_LCEnumeration"
	},

	"GetLCInteger": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_LCInteger",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "LC.Slot.1-1:AcPwrRcvryUserDelay"
			}
		}
	},

	"GetLCIntegers": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_LCInteger"
	},

	"GetLCString": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_LCString",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "DCIM_LCString:VAMAPP1"
			}
		}
	},

	"GetLCStrings": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_LCString"
	},

	"GetRemoteServicesAPIStatus": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService"
	},

	"GetRSStatus": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService"
	},

	"InsertCommentInLCLog": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService",
		PARAMS: {
			"Comment": {
				DEFAULT: None,
				EXAMPLE: "New comment"
			}
		}
	},

	"SetLCAttribute": {
		NAME: "SetAttribute",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService",
		PARAMS: {
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: "Collect System Inventory on Restart"
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: "Enabled"
			}
		}
	},

	"SetLCAttributes": {
		NAME: "SetAttributes",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService",
		PARAMS: {
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: ["Collect System Inventory on Restart", "Part Firmware Update"]
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: ["Enabled", "Allow version upgrade only"]
			}
		}
	},

	"ClearProvisioningServer": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService",
	},

	"ReInitiateDHS": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService",
		PARAMS: {
			"ProvisioningServer": {
				DEFAULT: None,
				EXAMPLE: "10.11.12.13"
			},
			"ResetToFactoryDefaults": {
				DEFAULT: None,
				EXAMPLE: "TRUE"
			},
			"PerformAutoDiscovery": {
				DEFAULT: None,
				EXAMPLE: "1"
			}
		}
	}
}

LICENSE_METHODS = {
	"DeleteLicense": {
		COMMAND: "invoke",
		URL: "EPR:DCIM_LicenseManagementService",
		PARAMS: {
			"EntitlementID": {
				DEFAULT: "",
				EXAMPLE: "Entitlement ID of the license to delete."
			},
			"FQDD": {
				DEFAULT: "",
				EXAMPLE: "FQDD of the device to delete the license from."
			},
			"DeleteOptions": {
				DEFAULT: "",
				EXAMPLE: "Flag to force delete or delete license from all like devices."
			}
		}
	},

	"GetLicensableDevice": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_LicensableDevice",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1"
			}
		}
	},

	"GetLicensableDevices": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_LicensableDevice"
	},

	"GetLicense": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_License",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1"
			}
		}
	},

	"GetLicenses": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_License"
	},

	"ReplaceLicense": {
		COMMAND: "invoke",
		URL: "EPR:DCIM_LicenseManagementService",
		PARAMS: {
			"EntitlementID": {
				DEFAULT: None,
				EXAMPLE: "Entitlement ID of the license being replaced."
			},
			"FQDD": {
				DEFAULT: None,
				EXAMPLE: "FQDD of the device the license is being replaced on."
			},
			"ReplaceOptions": {
				DEFAULT: None,
				EXAMPLE: "Flag to force or replace for all like devices. No options=0, force=1 and all=2."
			},
			"LicenseFile": {
				DEFAULT: None,
				EXAMPLE: "A base64 encoded XML License file."
			}
		}
	},

	"ImportLicense": {
		COMMAND: "invoke",
		URL: "EPR:DCIM_LicenseManagementService",
		PARAMS: {
			"ImportOptions": {
				DEFAULT: None,
				EXAMPLE: "Flag to force or install for all like devices. No options=0, force=1 and all=2."
			},
			"FQDD": {
				DEFAULT: None,
				EXAMPLE: "FQDD of the device to apply the License to."
			},
			"LicenseFile": {
				DEFAULT: None,
				EXAMPLE: "A base64 encoded XML License file."
			}
		}
	},

	"ExportLicenseToNetworkShare": {
		COMMAND: "invoke",
		URL: "EPR:DCIM_LicenseManagementService",
		PARAMS: {
			"UserName": {
				DEFAULT: "",
				EXAMPLE: "Username for CIFS share authentication"
			},
			"EntitlementID": {
				DEFAULT: None,
				EXAMPLE: "Entitlement ID of the license being exported"
			},
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "IP address of the machine hosting the NFS/CIFS share."
			},
			"ShareType": {
				DEFAULT: None,
				EXAMPLE: "Type of network share: 0 = NFS, 2 = CIFS"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name of the CIFS share or full path to the NFS share"
			},
			"FileName": {
				DEFAULT: "",
				EXAMPLE: "If included, the exported license is renamed to <FileName>"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "Password for CIFS share authentication"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "Name of the workgroup for CIFS share authentication."
			}
		}
	},

	"ExportLicense": {
		COMMAND: "invoke",
		URL: "EPR:DCIM_LicenseManagementService",
		PARAMS: {
			"EntitlementID": {
				DEFAULT: None,
				EXAMPLE: "Entitlement ID of the license being exported"
			}
		}
	},

	"ExportLicenseByDeviceToNetworkShare": {
		COMMAND: "invoke",
		URL: "EPR:DCIM_LicenseManagementService",
		PARAMS: {
			"UserName": {
				DEFAULT: "",
				EXAMPLE: "Username for CIFS share authentication"
			},
			"FQDD": {
				DEFAULT: None,
				EXAMPLE: "FQDD of the device to export licenses from"
			},
			"ShareType": {
				DEFAULT: None,
				EXAMPLE: "Type of network share: 0 = NFS, 2 = CIFS"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name of the CIFS share or full path to the NFS share"
			},
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "IP address of the machine hosting the NFS/CIFS share."
			},
			"FileName": {
				DEFAULT: "",
				EXAMPLE: "If included, the exported license is renamed to <FileName>"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "Password for CIFS share authentication"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "Name of the workgroup for CIFS share authentication."
			}
		}
	},

	"ExportLicenseByDevice": {
		COMMAND: "invoke",
		URL: "EPR:DCIM_LicenseManagementService",
		PARAMS: {
			"FQDD": {
				DEFAULT: None,
				EXAMPLE: "Entitlement ID of the license being exported"
			}
		}
	},

	"ImportLicenseFromNetworkShare": {
		COMMAND: "invoke",
		URL: "EPR:DCIM_LicenseManagementService",
		PARAMS: {
			"UserName": {
				DEFAULT: "",
				EXAMPLE: "Username for CIFS share authentication"
			},
			"ImportOptions": {
				DEFAULT: None,
				EXAMPLE: "Flag to force or install for all like devices. No options=0, force=1 and all=2."
			},
			"LicenseName": {
				DEFAULT: "",
				EXAMPLE: "If included, the exported license is renamed to <FileName>"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "Name of the workgroup for CIFS share authentication."
			},
			"FQDD": {
				DEFAULT: None,
				EXAMPLE: "Fully qualified device descriptor"
			},
			"ShareType": {
				DEFAULT: None,
				EXAMPLE: "Type of network share: 0 = NFS, 2 = CIFS"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name of the CIFS share or full path to the NFS share"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "Password for CIFS share authentication"
			},
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "IP address of the machine hosting the NFS/CIFS share."
			}
		}
	},

	"ShowLicenseBits": {
		COMMAND: "invoke",
		URL: "EPR:DCIM_LicenseManagementService",
	},
}

UPDATE_METHODS = {
	"GetSoftwareIdentity": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_SoftwareIdentity",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "DCIM:INSTALLED:NONPCI:160:0.43"
			}
		}
	},

	"GetSoftwareIdentities": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_SoftwareIdentity"
	},

	"InstallFromURI": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_SoftwareInstallationService?CreationClassName=DCIM_SoftwareInstallationService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=IDRAC:ID+Name=SoftwareUpdate",
		PARAMS: {
			"URI": {
				DEFAULT: None,
				EXAMPLE: ["http://[IP ADDRESS]/[PATH TO FILE.exe]",
					"cifs://[USERNAME]:[PASSWORD]@[URI-IP-ADDRESS]:[FILE.exe];mountpoint=/[DIRECTORYNAME]",
					"tftp://[IP ADDRESS]/[PATH TO FILE.exe]"]
			},
			"TargetRef": {
				DEFAULT: None,
				EXAMPLE: "DCIM:INSTALLED:NONPCI:160:0.43"
			}
		}
	}
}

SYSTEM_METHODS = {
	"CreateSystemConfigJob": {
		NAME: "CreateTargetedConfigJob",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_SystemManagementService?__cimnamespace=root/dcim+SystemCreationClassName=DCIM_ComputerSystem+SystemName=srv:system+CreationClassName=DCIM_SystemManagementService+Name=DCIM:SystemManagementService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "System.Embedded.1"
			},
			"RebootJobType": {
				DEFAULT: "",
				EXAMPLE: "3"
			},
			"ScheduledStartTime": {
				DEFAULT: "",
				EXAMPLE: "TIME_NOW"
			},
			"UntilTime": {
				DEFAULT: "",
				EXAMPLE: 20211111111111
			}
		}
	},

	"GetComputerSystems": {
		COMMAND: "enumerate",
		URL: "cimv2/CIM_ComputerSystem",
	},

	"GetCPUViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_CPUView"
	},

	"GetCPUView":{
		COMMAND: "get",
			URL: "cimv2/root/dcim/DCIM_CPUView",
			GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "CPU.Socket.1"
			}
		}
	},

	"GetFanViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_FanView"
	},

	"GetFanView":{
		COMMAND: "get",
			URL: "cimv2/root/dcim/DCIM_FanView",
			GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "Fan.Embedded.1"
			}
		}
	},

	"GetMemoryViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_MemoryView"
	},

	"GetMemoryView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_MemoryView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "DIMM.Slot.1"
			}
		}
	},

	"GetPCIDeviceViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_PCIDeviceView"
	},

	"GetPCIDeviceView":{
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_PCIDeviceView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "NIC.Integrated.1-1-1"
			}
		}
	},

	"GetPowerSupplyViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_PowerSupplyView"
	},

	"GetPowerSupplyView":{
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_PowerSupplyView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "PSU.Slot.1"
			}
		}
	},

	"GetSystemAttributes": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_SystemAttribute"
	},

	"GetSystemEnumerations": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_SystemEnumeration"
	},

	"GetSystemEnumeration": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_SystemEnumeration",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "System.Embedded.1#ServerPwr.1#PowerCapValue"
			}
		}
	},

	"GetSystemIntegers": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_SystemInteger"
	},

	"GetSystemInteger": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_SystemInteger",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "System.Embedded.1#ServerPwr.1#PowerCapValue"
			}
		}
	},

	"GetSystemStrings": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_SystemString"
	},

	"GetSystemString": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_SystemString",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "System.Embedded.1#ServerPwr.1#PowerCapValue"
			}
		}
	},

	"GetSystemViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_SystemView"
	},

	"GetSystemView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_SystemView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "System.Embedded.1"
			}
		}
	},

	"GetVideoViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_VideoView"
	},

	"GetVideoView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_VideoView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "Video.Embedded.1-1"
			}
		}
	},

	"SetSystemAttribute": {
		NAME: "SetAttribute",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_SystemManagementService?__cimnamespace=root/dcim+SystemCreationClassName=DCIM_ComputerSystem+SystemName=srv:system+CreationClassName=DCIM_SystemManagementService+Name=DCIM:SystemManagementService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "System.Embedded.1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: "DataCenterName"
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: "NEW Data Center Name"
			}
		}
	},

	"SetSystemAttributes": {
		NAME: "SetAttributes",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_SystemManagementService?__cimnamespace=root/dcim+SystemCreationClassName=DCIM_ComputerSystem+SystemName=srv:system+CreationClassName=DCIM_SystemManagementService+Name=DCIM:SystemManagementService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "System.Embedded.1"
			},
			"AttributeName": {
				DEFAULT: None,
				EXAMPLE: ["DataCenterName"]
			},
			"AttributeValue": {
				DEFAULT: None,
				EXAMPLE: ["NEW Data Center Name"]
			}
		}
	},

	"DeletePendingSystemConfiguration": {
		NAME: "DeletePendingConfiguration",
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_SystemManagementService?SystemCreationClassName=DCIM_ComputerSystem+SystemName=srv:system+CreationClassName=DCIM_SystemManagementService+Name=DCIM:SystemManagementService",
		PARAMS: {
			"Target": {
				DEFAULT: None,
				EXAMPLE: "System.Embedded.1"
			}
		}
	}
}

OSD_METHODS = {
	"BootToISOFromVFlash": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"BootToNetworkISO": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem",
		PARAMS: {
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "10.0.0.1"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name"
			},
			"ShareType": {
				DEFAULT: "2",
				EXAMPLE: "0=NFS, 2=CIFS"
			},
			"Username": {
				DEFAULT: "",
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "password"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			},
			"ImageName": {
				DEFAULT: None,
				EXAMPLE: "os.iso"
			}
		}
	},

 "DownloadISOToVFlash": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem",
		PARAMS: {
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "10.0.0.1"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name"
			},
			"ShareType": {
				DEFAULT: "2",
				EXAMPLE: "0=NFS, 2=CIFS"
			},
			"Username": {
				DEFAULT: "",
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "password"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			},
			"ImageName": {
				DEFAULT: None,
				EXAMPLE: "os.iso"
			}
		}
	},

	"BootToPXE": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"ConnectNetworkISOImage": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem",
		PARAMS: {
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "10.0.0.1"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name"
			},
			"ShareType": {
				DEFAULT: "2",
				EXAMPLE: "0=NFS, 2=CIFS"
			},
			"Username": {
				DEFAULT: "",
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "password"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			},
			"ImageName": {
				DEFAULT: None,
				EXAMPLE: "os.iso"
			}
		}
	},

	"DetachDrivers": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"DetachISOImage": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"DetachISOFromVFlash": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"DeleteISOFromVFlash": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"DisconnectNetworkISOImage": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"GetDriverPackInfo": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"GetHostMACInfo": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"GetNetworkISOImageConnectionInfo": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"GetOSDConcreteJob": {
		COMMAND: "get",
		URL: "cimv2/root/DCIM/DCIM_OSDConcreteJob",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "DCIM_OSDConcreteJob:1"
			}
		}
	},

	"GetOSDConcreteJobs": {
		COMMAND: "enumerate",
		URL: "cimv2/root/DCIM/DCIM_OSDConcreteJob"
	},

	"SkipISOImageBoot": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"UnpackAndAttach": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem",
		PARAMS: {
			"OSName": {
				DEFAULT: None,
				EXAMPLE: "Windows Server(R) 2008, x64"
			},
			"ExposeDuration": {
				DEFAULT: "",
				EXAMPLE: "00000000002200.000000:000"
			}
		}
	},

	"UnpackAndShare": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem",
		PARAMS: {
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "10.0.0.1"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name"
			},
			"ShareType": {
				DEFAULT: "2",
				EXAMPLE: "0=NFS, 2=CIFS"
			},
			"Username": {
				DEFAULT: "",
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "password"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			},
			"OSName": {
				DEFAULT: None,
				EXAMPLE: "Windows Server(R) 2008, x64"
			}
		}
	},

	"ConnectRFSISOImage": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem",
		PARAMS: {
			"IPAddress": {
				DEFAULT: None,
				EXAMPLE: "10.0.0.1"
			},
			"ShareName": {
				DEFAULT: None,
				EXAMPLE: "Name"
			},
			"ImageName": {
				DEFAULT: None,
				EXAMPLE: "imagename"
			},
			"ShareType": {
				DEFAULT: None,
				EXAMPLE: "0=NFS, 2=CIFS"
			},
			"Username": {
				DEFAULT: "",
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "password"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			},

		}
	},

	"DisconnectRFSISOImage": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"GetRFSISOImageConnectionInfo": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	},

	"BootToHD": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_OSDeploymentService?CreationClassName=DCIM_OSDeploymentService+Name=DCIM:OSDeploymentService+SystemCreationClassName=DCIM_ComputerSystem+SystemName=DCIM:ComputerSystem"
	}
}

ROLE_BASED_AUTHORIZATION = {
	"GetUsersAssignedLANPrivileges": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_IPMIRBAIdentityMemberOfCollection"
	},

	"GetUsersAssignedSerialOverLANPrivileges": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_IPMISOLRBAIdentityMemberOfCollection"
	},

	"GetUsersAssignedCLPPrivileges": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_CLPRBAIdentityMemberOfCollection"
	}
}

BOOT_METHODS = {
	"ChangeBootOrderByInstanceID": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_BootConfigSetting",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "IPL"
			}
		},
		PARAMS: {
			"source": {
				DEFAULT: None,
				EXAMPLE: ["IPL:Optical.SATAEmbedded.A-1:eb8aeb15796fb85f8e1447f0cfb8a68e"]
			}
		}
	},

	"ChangeBootSourceState": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_BootConfigSetting",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "IPL"
			}
		},
		PARAMS: {
			"source": {
				DEFAULT: None,
				EXAMPLE: "IPL:Optical.SATAEmbedded.A-1:eb8aeb15796fb85f8e1447f0cfb8a68e"
			},
			"EnabledState": {
				DEFAULT: None,
				EXAMPLE: 0
			}
		}
	},

	"GetBootConfigSetting": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_BootConfigSetting",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "UEFI"
			}
		}
	},

	"GetBootConfigSettings": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_BootConfigSetting"
	},

	"GetBootSourceSetting": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_BootSourceSetting",
		PARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "IPL:NIC.Embedded.1-1:68d139fb51afe60a5431e8ecca9562d5"
			}
		}
	},

	"GetBootSourceSettings": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_BootSourceSetting"
	},
}

BACKUP_RESTORE_METHODS = {
	"BackupImage": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService",
		PARAMS: {
			"IPAddress": {
				DEFAULT: "",
				EXAMPLE: "10.0.0.1"
			},
			"ShareName": {
				DEFAULT: "",
				EXAMPLE: "Name"
			},
			"ImageName": {
				DEFAULT: "",
				EXAMPLE: "backup.img"
			},
			"ShareType": {
				DEFAULT: "4",
				EXAMPLE: "0=NFS, 2=CIFS, 4=vFlash"
			},
			"Username": {
				DEFAULT: "",
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "password"
			},
			"Passphrase": {
				DEFAULT: "",
				EXAMPLE: "cryptic"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			},
			"ScheduledStartTime": {
				DEFAULT: "",
				EXAMPLE: "TIME_NOW"
			},
			"UntilTime": {
				DEFAULT: "",
				EXAMPLE: 20211111111111
			}
		}
	},

	"RestoreImage": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_LCService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_LCService+SystemName=DCIM:ComputerSystem+Name=DCIM:LCService",
		PARAMS: {
			"IPAddress": {
				DEFAULT: "",
				EXAMPLE: "10.0.0.1"
			},
			"ShareName": {
				DEFAULT: "",
				EXAMPLE: "Name"
			},
			"ImageName": {
				DEFAULT: "",
				EXAMPLE: "backup.img"
			},
			"ShareType": {
				DEFAULT: "4",
				EXAMPLE: "0=NFS, 2=CIFS, 4=vFlash"
			},
			"Username": {
				DEFAULT: "",
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: "",
				EXAMPLE: "password"
			},
			"Passphrase": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "WORKGROUP"
			},
			"ScheduledStartTime": {
				DEFAULT: "",
				EXAMPLE: "TIME_NOW"
			},
			"UntilTime": {
				DEFAULT: "",
				EXAMPLE: 20211111111111
			},
			"PreserveVDConfig": {
				DEFAULT: "0",
				EXAMPLE: "1"
			}
		}
	}
}

PROFILE_METHODS = {
	"GetCIMRegisteredProfiles": {
		COMMAND: "enumerate",
		URL: "cimv2/DCIM_RegisteredProfile",
		GETPARAMS: {
			"__cimnamespace": {
				DEFAULT: "root/interop"
			}
		}
	},

	"GetCIMRegisteredProfile": {
		COMMAND: "get",
		URL: "cimv2/DCIM_RegisteredProfile",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "DCIM:PhysicalAssetRegisteredProfile:1"
			},
			"__cimnamespace": {
				DEFAULT: "root/interop"
			}
		}
	},

	"GetLCRegisteredProfiles": {
		COMMAND: "enumerate",
		URL: "cimv2/DCIM_LCRegisteredProfile",
		GETPARAMS: {
			"__cimnamespace": {
				DEFAULT: "root/interop"
			}
		}
	},

	"GetLCRegisteredProfile": {
		COMMAND: "get",
		URL: "cimv2/DCIM_LCRegisteredProfile",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "DCIM:CPU:1.0.0"
			},
			"__cimnamespace": {
				DEFAULT: "root/interop"
			}
		}
	}
}

SERVICE_METHODS = {
	"GetEPR": {
		COMMAND: "enumerate",
		URL: "cimv2/",
		GETPARAMS: {
			"Class": {
				DEFAULT: None,
				EXAMPLE: "CIM_PowerManagementService"
			}
		}
	},

	"GetClass": {
		COMMAND: "enumerate",
		URL: "cimv2/",
		GETPARAMS: {
			"Class": {
				DEFAULT: None,
				EXAMPLE: "CIM_PowerManagementCapabilities"
			}
		}
	},

	"GetInstance": {
		COMMAND: "get",
		URL: "cimv2/",
		GETPARAMS: {
			"Class": {
				DEFAULT: None,
				EXAMPLE: "CIM_PowerManagementCapabilities"
			},
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "NIC.Integrated.1-1-1"
			}
		}
	},

	"GetAssociatedPowerManagementService": {
		COMMAND: "enumerate",
		URL: "cimv2/CIM_AssociatedPowerManagementService"
	},

	"GetEFConfigurationService": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_EFConfigurationService"
	},

	"GetPowerManagementService": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_PowerManagementService"
	},
	
	"Identify": {
		COMMAND: "identify"
	}
}

EVENT_FILTER_METHODS = {
	"GetEventFilterViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_EventFilter"
	},

	"GetEventFilterView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_EventFilter",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1#RACEvtFilterCfgRoot#MEM_1_1"
			}
		}
	},

	"SetEventFilterByCategory": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_EFConfigurationService?Name=DCIM:EFConfigurationService+CreationClassName=DCIM_EFConfigurationService+SystemName=systemmc+SystemCreationClassName=DCIM_SPComputerSystem",
		PARAMS: {
			"Category": {
				DEFAULT: ""
			},
			"SubCategory": {
				DEFAULT: ""
			},
			"Severity": {
				DEFAULT: ""
			},
			"RequestedAction": {
				DEFAULT: "",
				EXAMPLE: "0,1,2,3"
			},
			"RequestedNotification": {
				DEFAULT: "",
				EXAMPLE: "0,1,2,3,4,5"
			}
		}
	},

	"SetEventFilterByInstanceIDs": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_EFConfigurationService?Name=DCIM:EFConfigurationService+CreationClassName=DCIM_EFConfigurationService+SystemName=systemmc+SystemCreationClassName=DCIM_SPComputerSystem",
		PARAMS: {
			"InstanceID": {
				DEFAULT: ""
			},
			"RequestedAction": {
				DEFAULT: "",
				EXAMPLE: "0,1,2,3"
			},
			"RequestedNotification": {
				DEFAULT: "",
				EXAMPLE: "0,1,2,3,4,5"
			}
		}
	}
}

SENSOR_METHODS = {
	"SetSensorThreshold":{
		COMMAND: "set",
		URL: "cimv2/root/dcim/DCIM_PSNumericSensor",
		GETPARAMS: {
			"__cimnamespace": {
				DEFAULT: "root/dcim"
			},
			"SystemCreationClassName": {
				DEFAULT: "DCIM_ComputerSystem"
			},
			"SystemName": {
				DEFAULT: "srv:system"
			},
			"CreationClassName": {
				DEFAULT: "DCIM_PSNumericSensor"
			},
			"DeviceID": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1#PS2Current2"
			},
		},
		PARAMS: {
			"LowerThresholdNonCritical": {
				DEFAULT: None,
				EXAMPLE: "25"
			},
			"UpperThresholdNonCritical": {
				DEFAULT: None,
				EXAMPLE: "1025"
			}
		}
	},

	"GetSensorView":{
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_PSNumericSensor",
		GETPARAMS: {
			"__cimnamespace": {
				DEFAULT: "root/dcim"
			},
			"SystemCreationClassName": {
				DEFAULT: "DCIM_ComputerSystem"
			},
			"SystemName": {
				DEFAULT: "srv:system"
			},
			"CreationClassName": {
				DEFAULT: "DCIM_PSNumericSensor"
			},
			"DeviceID": {
				DEFAULT: None,
				EXAMPLE: "iDRAC.Embedded.1#PS2Current2"
			},
		}
	},

	"GetSensorViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/CIM_Sensor"
	}
}

RECORD_LOG_METHODS = {
	"SetLCLogEntryComment": {
		COMMAND: "set",
		URL: "cimv2/root/dcim/DCIM_LCLogEntry",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "DCIM:LifeCycleLog:49420"
			}
		},
		PARAMS: {
			"Comment": {
				DEFAULT: None,
				EXAMPLE: "any comment"
			}
		}
	},

	"GetLCLogEntry": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_LCLogEntry",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "DCIM:LifeCycleLog:49420"
			}
		}
	},

	"GetLCRecordLogs": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_LCRecordLog"
	},

	"GetLCRecordLogCapabilities": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_LCRecordLogCapabilities"
	},

	"GetLCLogEntries": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_LCLogEntry"
	},

	"GetSystemEventLogs": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_SELRecordLog"
	},

	"GetSystemEventLogCapabilities": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_SELRecordLogCapabilities"
	},

	"GetSystemEventLogEntries": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_SELLogEntry"
	}
}

VFLASH_MANAGEMENT_METHODS = {
	"GetVFlashPartitionViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_OpaqueManagementData"
	},

	"GetVFlashViews": {
		COMMAND: "enumerate",
		URL: "cimv2/root/dcim/DCIM_VFlashView"
	},

	"GetVFlashView": {
		COMMAND: "get",
		URL: "cimv2/root/dcim/DCIM_VFlashView",
		GETPARAMS: {
			"InstanceID": {
				DEFAULT: None,
				EXAMPLE: "Disk.vFlashCard.1"
			}
		}
	},

	"InitializeMedia": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_PersistentStorageService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_PersistentStorageService+SystemName=DCIM:ComputerSystem+Name=DCIM:PersistentStorageService",
	},

	"CreatePartition": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_PersistentStorageService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_PersistentStorageService+SystemName=DCIM:ComputerSystem+Name=DCIM:PersistentStorageService",
		PARAMS: {
			"PartitionIndex": {
				DEFAULT: None,
				EXAMPLE: "16"
			},
			"Size": {
				DEFAULT: None,
				EXAMPLE: ""
			},
			"SizeUnit": {
				DEFAULT: "",
				EXAMPLE: "MB = 1, GB = 2"
			},
			"PartitionType": {
				DEFAULT: "",
				EXAMPLE: "floppy=1, hard disk=2"
			},
						"OSVolumeLabel": {
				DEFAULT: "",
				EXAMPLE: ""
			}
		}
	},

	"DeletePartition": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_PersistentStorageService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_PersistentStorageService+SystemName=DCIM:ComputerSystem+Name=DCIM:PersistentStorageService",
		PARAMS: {
			"PartitionIndex": {
				DEFAULT: None,
				EXAMPLE: "16"
			}
		}
	},

	"FormatPartition": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_PersistentStorageService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_PersistentStorageService+SystemName=DCIM:ComputerSystem+Name=DCIM:PersistentStorageService",
		PARAMS: {
			"PartitionIndex": {
				DEFAULT: None,
				EXAMPLE: "16"
			},
			"FormatType": {
				DEFAULT: None,
				EXAMPLE: "RAW=0, EXT2=1, EXT3=2, FAT16=3, FAT32=4"
			}
		}
	},


	"VFlashStateChange": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_PersistentStorageService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_PersistentStorageService+SystemName=DCIM:ComputerSystem+Name=DCIM:PersistentStorageService",
		PARAMS: {
			"RequestedState": {
				DEFAULT: None,
				EXAMPLE: "Enable=1, Disable=2"
			}
		}
	},

	"CreatePartitionUsingImage": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_PersistentStorageService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_PersistentStorageService+SystemName=DCIM:ComputerSystem+Name=DCIM:PersistentStorageService",
		PARAMS: {
			"PartitionIndex": {
				DEFAULT: None,
				EXAMPLE: "16"
			},
			"PartitionType": {
				DEFAULT: None,
				EXAMPLE: "floppy=1, hard disk=2"
			},
			"OSVolumeLabel": {
				DEFAULT: None,
				EXAMPLE: ""
			},
			"URI": {
				DEFAULT: "",
				EXAMPLE: ""
			},
			"IPAddress": {
				DEFAULT: "",
				EXAMPLE: "10.0.0.1"
			},
			"ShareType": {
				DEFAULT: None,
				EXAMPLE: "0=NFS, 2=CIFS"
			},
			"SharePath": {
				DEFAULT: "",
				EXAMPLE: "path"
			},
			"ImageName": {
				DEFAULT: None,
				EXAMPLE: "os.iso"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "Name"
			},
			"Username": {
				DEFAULT: None,
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: None,
				EXAMPLE: "password"
			},
			"Port": {
				DEFAULT: "",
				EXAMPLE: "Port"
			},
			"HashType": {
				DEFAULT: "",
				EXAMPLE: "HashType"
			},
			"HashValue": {
				DEFAULT: "",
				EXAMPLE: "HashValue"
			}
		}
	},

	"ModifyPartition": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_PersistentStorageService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_PersistentStorageService+SystemName=DCIM:ComputerSystem+Name=DCIM:PersistentStorageService",
		PARAMS: {
			"PartitionIndex": {
				DEFAULT: None,
				EXAMPLE: "16"
			},
			"AccessType": {
				DEFAULT: "",
				EXAMPLE: "Read-Only=1, Read-Write=3"
			}
		}
	},

	"AttachPartition": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_PersistentStorageService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_PersistentStorageService+SystemName=DCIM:ComputerSystem+Name=DCIM:PersistentStorageService",
		PARAMS: {
			"PartitionIndex": {
				DEFAULT: None,
				EXAMPLE: "16"
			}
		}
	},

	"DetachPartition": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_PersistentStorageService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_PersistentStorageService+SystemName=DCIM:ComputerSystem+Name=DCIM:PersistentStorageService",
		PARAMS: {
			"PartitionIndex": {
				DEFAULT: None,
				EXAMPLE: "16"
			}
		}
	},

	"ExportDataFromPartition": {
		COMMAND: "invoke",
		URL: "cimv2/root/dcim/DCIM_PersistentStorageService?SystemCreationClassName=DCIM_ComputerSystem+CreationClassName=DCIM_PersistentStorageService+SystemName=DCIM:ComputerSystem+Name=DCIM:PersistentStorageService",
		PARAMS: {
			"PartitionIndex": {
				DEFAULT: None,
				EXAMPLE: "16"
			},
			"IPAddress": {
				DEFAULT: "",
				EXAMPLE: "10.0.0.1"
			},
			"ShareType": {
				DEFAULT: None,
				EXAMPLE: "0=NFS, 2=CIFS"
			},
			"SharePath": {
				DEFAULT: "",
				EXAMPLE: "path"
			},
			"ImageName": {
				DEFAULT: None,
				EXAMPLE: "os.iso"
			},
			"Workgroup": {
				DEFAULT: "",
				EXAMPLE: "Name"
			},
			"Username": {
				DEFAULT: None,
				EXAMPLE: "username"
			},
			"Password": {
				DEFAULT: None,
				EXAMPLE: "password"
			},
			"Port": {
				DEFAULT: "",
				EXAMPLE: "Port"
			}
		}
	}
}

LC_AREAS = [
	"BACKUP_RESTORE_METHODS",
	"BIOS_METHODS",
	"BOOT_METHODS",
	"EVENT_FILTER_METHODS",
	"FC_METHODS",
	"iDRAC_METHODS",
	"JOB_METHODS",
	"LC_METHODS",
	"LICENSE_METHODS",
	"NIC_METHODS",
	"OSD_METHODS",
	"POWER_METHODS",
	"PROFILE_METHODS",
	"RAID_METHODS",
	"RECORD_LOG_METHODS",
	"ROLE_BASED_AUTHORIZATION",
	"SENSOR_METHODS",
	"SERVICE_METHODS",
	"SYSTEM_METHODS",
	"UPDATE_METHODS",
	"VFLASH_MANAGEMENT_METHODS"
]

METHODS = {}
for lc_area in LC_AREAS:
	METHODS.update(eval(lc_area))

class Log(object):
	def __init__(self, name, mode):
		self.file = open(name, mode)
		self.stdout = sys.stdout
		sys.stdout = self
	def close(self):
		sys.stdout = self.stdout
		self.file.close()
	def write(self, data):
		self.file.write(data)
		self.file.flush()
		self.stdout.write(data)

###
# XML interop

def gettype(obj):
	if type(obj) in [types.StringType, types.UnicodeType]: return 'str'
	elif type(obj) == types.IntType: return 'int'
	elif type(obj) == types.LongType: return 'long'
	elif type(obj) == types.FloatType: return 'float'
	elif type(obj) == types.BooleanType: return 'bool'
	elif type(obj) == types.DictType: return 'dict'
	elif type(obj) == types.NoneType: return 'null'
	elif type(obj) in [types.ListType, types.TupleType]: return 'list'

	print "Unknown type: %s" % type(obj)
	sys.exit()

def obj2xml(obj, name=None):
	x = obj2xml_int(obj, name)
	x = xml.dom.minidom.parseString(x)
	return x

def obj2xml_int(obj, name=None):
	if name == None:
		i = None
		for i in globals():
			if i == "obj": continue
			if globals()[i] == obj: name = i

	_type = gettype(obj)

	if _type == "dict":
		items = ""
		for key in obj: items += obj2xml_int(obj[key], key)
		return OBJECT % (_type, name, items)
	elif _type == "list":
		items = ""
		for val in obj: items += obj2xml_int(val)
		return OBJECT % (_type, name, items)
	elif _type == "null":
		return OBJECT % (_type, name, "")
	elif _type == "str":
		return OBJECT % (_type, name, obj.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;"))

	return OBJECT % (_type, name, obj)

def xml2obj(x):
	if not x.hasAttributes(): return None, None

	obj = None
	name = ""
	_type = ""
	if x.hasAttribute("name"): name = x.getAttribute("name")
	if x.hasAttribute("type"): _type = x.getAttribute("type")

	if _type == "dict":
		obj = {}
		if x.hasChildNodes():
			for child in x.childNodes:
				cname, val = xml2obj(child)
				obj[cname] = val
	elif _type == "list":
		obj = []
		if x.hasChildNodes():
			for child in x.childNodes:
				cname, val = xml2obj(child)
				obj.append(val)
	elif _type == "null":
		obj = None
	else:
		if x.hasChildNodes() and x.firstChild.nodeType == x.TEXT_NODE:
			obj = x.firstChild.data.encode("ascii")

	return name.encode("ascii"), obj

def remove_xmltag(data):
	return re.sub('<\?xml version=.*?>', '', data)

def toprettyxml(x):
	text_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)
	return re.sub("(?imu)^\s*\n", "", text_re.sub('>\g<1></', remove_xmltag(x.toprettyxml(indent=" "))))

def getNodeText(nodelist):
	rc = ""
	for node in nodelist:
		if node.nodeType == node.TEXT_NODE:
			rc += node.data
		else:
			return None
	return rc.strip()

###
# Command building

def makeparam(nvpairs):
	params = {}
	for nvpair in nvpairs:
		nvpair = nvpair.split("=", 1)
		if len(nvpair) == 2:
			if not nvpair[0] in params.keys():
				params[nvpair[0]] = []
			params[nvpair[0]].append(nvpair[1])
		else:
			print "Skipping '%s' not in name=value format" % nvpair
	return params

def parsecmd(command):
	command = shlex.split(command.strip())
	method = command.pop(0)
	params = makeparam(command)

	return method, params

def getfilemode(mdata):
	filemode = False

	if PARAMS in mdata.keys():
		mparams = mdata[PARAMS].keys()
		for param in mparams:
			try: test = mdata[PARAMS][param][EXAMPLE]
			except: test = mdata[PARAMS][param][DEFAULT]

			if type(test) == types.ListType or (type(test) == types.StringType and "EPR" in test):
				filemode = True
				break

	return filemode

def buildparams(mdata, paramtype, method, params, eprselect, filemode, fnumber):
	cmd = ""

	mparams = mdata[paramtype].keys()
	mparams.sort()

	for param in mparams:
		if not param in params.keys():
			default = mdata[paramtype][param][DEFAULT]
			if default == None:
				if VAR_LINE in VARIABLES: print "%d: " % VARIABLES[VAR_LINE],
				print "Required parameter '%s' missing for method '%s'" % (param, method)
				return None
			elif default == "":
				continue

			source = default
		else:
			source = params[param]

		if type(source) != types.ListType:
			source = [source]

		for val in source:
			if paramtype == GETPARAMS:
				if method in METAMETHODS and param == "Class":
					cmd += "%s?" % val
				else:
					cmd += "%s=%s+" % (param, val)
			else:
				if filemode == True:
					if param == "TargetRef":
						os.write(fnumber, getaddressxml("Target", "http://schemas.dell.com/wbem/wscim/1/cim-schema/2/DCIM_SoftwareIdentity", {"InstanceID": val}))
					elif type(val) == types.StringType and "EPR:" in val:
						address = get_cached_epr(val, param, eprselect)
						if address == None:
							address = buildaddress(method, val, param, eprselect)
							if address == None:
								return None

							set_cached_epr(val, param, eprselect, address)

						os.write(fnumber, address)
					else:
						os.write(fnumber, "  <p:%s>%s</p:%s>\r\n" % (param, val, param))
				else:
					if "win" in sys.platform:
						cmd += "%s=\"%s\";" % (param, val)
					else:
						cmd += " -k \"%s=%s\"" % (param, val)

	if paramtype == GETPARAMS:
		cmd = cmd[:-1]
	else:
		if not filemode and "win" in sys.platform:
			cmd = cmd[:-1] + "}"

	return cmd

def buildcmd(command):
	global TEMPFILES
	global VARIABLES
	global VAR_LINE

	method, params = parsecmd(command)

	if method in METHODS.keys():
		mdata = METHODS[method]
	else:
		if VAR_LINE in VARIABLES: print "%d: " % VARIABLES[VAR_LINE],
		print "Invalid method '%s'" % method.replace("\\\\", "\\")
		return None, None

	if NAME in mdata:
		api = mdata[NAME]
	else:
		api = method

	if "win" in sys.platform:
		cmd = "winrm"
	else:
		cmd = "wsman"

	cmd += " %s" % mdata[COMMAND]
	if mdata[COMMAND] == "invoke":
		if not "win" in sys.platform:
			cmd += " -a"
		cmd += " %s" % api

	eprselect = {}
	for param in params:
		if param == "-eprselect":
			try:
				eprselect = params[param][0]
			except:
				print "Invalid syntax for -eprselect=Name=Value,Param:Name=Value,..."
				return None

			eprselect = parse_eprselect(eprselect)

			break

	filemode = getfilemode(mdata)
	if URL in mdata:
		url = mdata[URL]
		if "EPR" in mdata[URL]:
			url = get_cached_epr(mdata[URL], URL, eprselect)
			if url == None:
				url = buildurl(method, mdata[URL], eprselect)
				if url == None:
					return None, None

				set_cached_epr(mdata[URL], URL, eprselect, url)

		if filemode == True:
			(fnumber, fname) = tempfile.mkstemp()
			if "http://" in url:
				os.write(fnumber, "<p:%s_INPUT xmlns:p=\"%s\">\r\n" % (api, url.split("?")[0]))
			else:
				os.write(fnumber, "<p:%s_INPUT xmlns:p=\"http://schemas.dmtf.org/wbem/wscim/1/cim-schema/%s\">\r\n" % (api, url.split("?")[0][4:]))
		else:
			fnumber = None

		if "win" in sys.platform:
			cmd += ' "%s' % url
		else:
			cmd += ' "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/%s' % url[4:].replace("+", ",")

		if GETPARAMS in mdata:
			if not method in METAMETHODS:
				cmd += "?"

			pars = buildparams(mdata, GETPARAMS, method, params, eprselect, filemode, fnumber)
			if pars == None:
				return None, None
			cmd += pars
		cmd += '"'

	if PARAMS in mdata.keys():
		if not filemode and "win" in sys.platform:
			cmd += " @{"
		pars = buildparams(mdata, PARAMS, method, params, eprselect, filemode, fnumber)
		if pars == None:
			return None, None
		cmd += pars

	ip = getip()
	if ip == None:
		return None, None

	port = PORTDEFAULT
	if PORT in VARIABLES.keys():
		port = VARIABLES[PORT]

	if "win" in sys.platform:
		cmd += " -r:https://%s:%s/wsman" % (ip, port)
	else:
		cmd += " -h %s" % ip
		cmd += " -P %s" % port

	if LOGIN in VARIABLES.keys():
		cmd += " -u"
		if "win" in sys.platform:
			cmd += ":"
		else:
			cmd += " "
		cmd += "%s" % VARIABLES[LOGIN]
	else:
		print "Login ID undefined. --> Set $LOGIN username"
		return None, None

	if PASS in VARIABLES.keys():
		cmd += " -p"
		if "win" in sys.platform:
			cmd += ":"
		else:
			cmd += " "
		cmd += "%s" % VARIABLES[PASS]
	else:
		print "Password undefined. --> Set $PASSWORD password"
		return None, None

	if "win" in sys.platform:
		cmd += " -SkipCNcheck -SkipCAcheck -SkipRevocationCheck -encoding:utf-8 -a:basic -format:pretty"
	else:
		cmd += " -V -v -c dummy.cert -j utf-8 -y basic"

	if "-cql" in params.keys() or "-wql" in params.keys() or "-assoc" in params.keys():
		if "-wql" in params.keys():
			filt = "-wql"
			dialect = "http://schemas.microsoft.com/wbem/wsman/1/WQL"
		elif "-assoc" in params.keys():
			filt = "-assoc"
			dialect = "http://schemas.dmtf.org/wbem/wsman/1/cimbinding/associationFilter"
		else:
			filt = "-cql"
			dialect = "http://schemas.dmtf.org/wbem/cql/1/dsp0202.pdf"

		if "win" in sys.platform:
			cmd += " -dialect:%s -filter:\"%s\"" % (dialect, params[filt][0])
		else:
			cmd += " --dialect=%s --filter=\"%s\"" % (dialect, params[filt][0])

	if method == "GetEPR":
		if "win" in sys.platform:
			cmd += " -returntype:EPR"
		else:
			cmd += " -M epr"

	if filemode:
		os.write(fnumber, "</p:%s_INPUT>\r\n" % api)
		os.close(fnumber)

		if "win" in sys.platform:
			cmd += " -file:"
		else:
			cmd += " -J "
		cmd += "%s" % fname

		TEMPFILES.append(fname)

	return cmd, method

###
# Address generation using EPR

def getepr(method, _class):
	global OUTPUTXMLOBJ

	_class = _class.split(":")
	if len(_class) != 2:
		print "Invalid EPR declaration for method '%s'" % method
		return None

	_class = _class[1]
	run("GetEPR Class=%s" % _class)
	if OUTPUTXMLOBJ == None:
		print "GetEPR failed for class '%s'" % _class
		return None

	return OUTPUTXMLOBJ

def getselectors(x, param, eprselect):
	fname = ""
	fvalue = ""
	eprnv = ""
	if param in eprselect:
		eprnv = eprselect[param]
	elif GLOBAL in eprselect:
		eprnv = eprselect[GLOBAL]

	if eprnv:
		eprnv = eprnv.split("=", 1)
		if len(eprnv) == 2:
			fname = eprnv[0]
			fvalue = eprnv[1]

	found = False
	instance = 0
	ns = "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
	xselectorsets = x.getElementsByTagNameNS(ns, "SelectorSet")
	for xselectorset in xselectorsets:
		selectors = {}
		xselectors = xselectorset.getElementsByTagNameNS(ns, "Selector")
		for selector in xselectors:
			name = selector.getAttribute("Name").encode("ascii")
			value = selector.firstChild.data.encode("ascii")
			if name:
				selectors[name] = value

				if name == fname and value == fvalue:
					found = True

		if found == True:
			break

		if fname == "" and fvalue == "":
			found = True
			break

		instance += 1

	if found == False:
		print "EPR filter failed - '%s' not found" % eprselect
		return None, None

	return selectors, instance

def getaddressobj(method, _class, param, eprselect):
	x = getepr(method, _class)
	if x == None:
		return None, None

	selectors, instance = getselectors(x, param, eprselect)
	if selectors == None:
		return None, None

	ns = "http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd"
	rURI = x.getElementsByTagNameNS(ns, "ResourceURI")
	if len(rURI) < instance+1:
		print "EPR:x:Class declaration for method '%s' where x > instances" % method
		return None, None

	url = rURI[instance].firstChild.data.encode("ascii")

	return url, selectors

def getaddressxml(param, url, selectors):
	global ADDRESSREF
	global SELECTORREF

	selectorsstr = ""
	for selector in selectors.keys():
		selectorsstr += SELECTORREF % (selector, selectors[selector]) + "\n"

	addressstr = ADDRESSREF % (param, url, selectorsstr[:-1], param)

	return addressstr

def buildurl(method, _class, eprselect):
	url, selectors = getaddressobj(method, _class, URL, eprselect)
	if url == None:
		return None

	selectorsstr = ""
	for selector in selectors.keys():
		selectorsstr += "%s=%s+" % (selector, selectors[selector])

	if selectorsstr:
		url = "%s?%s" % (url, selectorsstr[:-1])

	return url

def buildaddress(method, _class, param, eprselect):
	url, selectors = getaddressobj(method, _class, param, eprselect)
	if url == None:
		return None

	addressstr = getaddressxml(param, url, selectors)

	return addressstr

def get_cached_epr(_class, param, eprselect):
	global CACHED_EPR

	ip = getip()
	if ip == None: return

	if param in eprselect:
		param += "-" + eprselect[param]
	elif GLOBAL in eprselect:
		param += "-" + eprselect[GLOBAL]

	if ip in CACHED_EPR and _class in CACHED_EPR[ip] and param in CACHED_EPR[ip][_class]:
		return CACHED_EPR[ip][_class][param]

	return None

def set_cached_epr(_class, param, eprselect, value):
	global CACHED_EPR

	ip = getip()
	if ip == None: return

	if not ip in CACHED_EPR:
		CACHED_EPR[ip] = {}

	if not _class in CACHED_EPR[ip]:
		CACHED_EPR[ip][_class] = {}

	if param in eprselect:
		param += "-" + eprselect[param]
	elif GLOBAL in eprselect:
		param += "-" + eprselect[GLOBAL]

	CACHED_EPR[ip][_class][param] = value

def parse_eprselect(eprselects):
	eprobj = {}
	eprselects = eprselects.split(",")
	for eprselect in eprselects:
		specific = eprselect.split("|", 1)
		if len(specific) == 1:
			# Global EPRselect
			eprobj[GLOBAL] = specific[0]
		elif len(specific) == 2:
			# Specific EPRselect
			eprobj[specific[0]] = specific[1]

	return eprobj

###
# Internal methods

def batchrun(cmd):
	cmd = shlex.split(cmd)

	if len(cmd) != 2:
		help("help batch")
		print "\nRequire 1 argument"
		return None

	fname = replvars(cmd[1])
	return batch(fname)

def context(cmd):
	global CONTEXT
	global OUTPUT

	cmd = shlex.split(cmd)
	if len(cmd) < 3:
		help("help context")
		print "\nRequire 2 or more arguments"
		return None

	look = replvars(cmd[1]).split("=")
	if len(look) != 2:
		help("help context")
		print "\nFormat of argument 1 incorrect"
		return None

	ret = find("Find %s=\"%s\"" % (look[0], look[1]), True)
	if not ret:
		print "Context %s=%s not found" % (look[0], look[1])
		return ret

	fcmd = " ".join([quote_string(i) for i in cmd[2:]])
	ret = process(fcmd)
	CONTEXT = None

	return ret

def count(cmd):
	global OUTPUT
	global VARIABLES

	cmd = shlex.split(cmd)
	if len(cmd) != 2:
		help("help count")
		print "\nRequire 1 argument"
		return None

	VARIABLES[cmd[1]] = OUTPUT.count("\n\n")

	return True

def find(cmd, context=False):
	global CONTEXT
	global VARIABLES
	global VAR_FIND
	global VAR_PARENT

	cmd = shlex.split(cmd)
	if len(cmd) < 2:
		help("help find")
		print "\nRequire 1 or more arguments"
		return None

	lookval = None
	look = replvars(cmd[1]).split("=")
	if len(look) == 2:
		lookval = look[1]
	look = look[0]

	var = None
	if len(cmd) > 2:
		var = cmd[2]

	if lookval != None:
		inst = None
	else:
		inst = 1

	if len(cmd) > 3:
		try:
			inst = int(replvars(cmd[3]))
			if inst < 1:
				raise Exception
		except:
			return None

	if var in VARIABLES.keys():
		del VARIABLES[var]

	ret = findall("Findall %s %s" % (look, VAR_FIND), inst)
	if not ret:
		return ret

	if lookval != None:
		if not inst:
			if not lookval in VARIABLES[VAR_FIND]:
				ret = False
			else:
				for i in range(len(VARIABLES[VAR_FIND])):
					if VARIABLES[VAR_FIND][i] == lookval:
						VARIABLES[VAR_FIND] = lookval
						if context:
							CONTEXT = VARIABLES[VAR_PARENT][i]

						break
		else:
			if lookval != VARIABLES[VAR_FIND]:
				ret = False
			else:
				if context:
					CONTEXT = VARIABLES[VAR_PARENT]

	if var != None:
		if not VAR_FIND in VARIABLES:
			ret = False
		else:
			VARIABLES[var] = VARIABLES[VAR_FIND]

	del VARIABLES[VAR_PARENT]
	del VARIABLES[VAR_FIND]

	return ret

def findall(cmd, inst=None):
	global CONTEXT
	global OUTPUTXMLOBJ
	global VARIABLES
	global VAR_FIND
	global VAR_PARENT

	cmd = shlex.split(cmd)
	if len(cmd) != 3:
		help("help findall")
		print "\nRequire 2 arguments"
		return None

	look = cmd[1]
	var = cmd[2]

	if var in VARIABLES.keys():
		del VARIABLES[var]

	results = []
	parents = []
	if CONTEXT != None:
		x = CONTEXT
	else:
		x = OUTPUTXMLOBJ

	def recurse_findall(node, key):
		if node == None:
			return

		if node.nodeName != "":
			name = node.nodeName.split(":")
			if len(name) == 2 and ((name[1] == key) or (name[1] == "Selector" and node.getAttribute("Name") == key)):
					text = getNodeText(node.childNodes)
					if text != None:
						results.append(text.encode("ascii"))
						parents.append(node.parentNode)
						return

		for child in node.childNodes:
			recurse_findall(child, key)
			if inst != None and len(results) == inst:
				return

	recurse_findall(x, look)
	if len(results):
		if inst != None:
			if len(results) == inst:
				VARIABLES[var] = results[inst-1]
				if var == VAR_FIND:
					VARIABLES[VAR_PARENT] = parents[inst-1]
				return True
		else:
			VARIABLES[var] = results
			if var == VAR_FIND:
				VARIABLES[VAR_PARENT] = parents
			return True

	return False

def gosub(cmd):
	return goto(cmd, True)

def goto(cmd, sub=False):
	global GOTO
	global BATCH
	global VARIABLES
	global VAR_LINE

	if not len(BATCH):
		print "\nNot in batch mode"
		return None

	cmd = shlex.split(cmd)
	if len(cmd) != 2:
		help("help goto")
		print "\nRequire 1 argument"
		return None

	ll = replvars(cmd[1])
	if len(ll.split(":")) == 2:
		ret = batch(ll, sub)
		if sub == False:
			GOTO = len(BATCH[-1])
		return ret

	try:
		GOTO = int(ll) - 1
		if sub == True: RETURN.append(VARIABLES[VAR_LINE]+1)
		return True
	except:
		for i in range(len(BATCH[-1])):
			if BATCH[-1][i].strip() == ":" + ll:
				GOTO = i
				if sub == True: RETURN.append(VARIABLES[VAR_LINE]+1)
				return True

	return False

def help(command):
	global PROGRAM
	global VARIABLES

	if command == "help":
		if VARIABLES[PROGRAM] == True:
			areas = [eval(area) for area in LC_AREAS]
			x = obj2xml(areas, "LC_AREAS")
			print x.toxml()
			return

		length = max([len(i) for i in METHODS.keys()]) + 1
		form = "%%-%ds" % length
		numpline = 80/length

		internal = INTERNAL.keys()
		internal.sort()
		count = 1
		print "\nINTERNAL METHODS"
		print "----------------"
		for i in range(len(internal)):
			print form % internal[i],
			if count % numpline == 0 and i != len(internal)-1: print
			count += 1
		print

		for lc_area in LC_AREAS:
			print "\n" + lc_area.replace("_", " ")
			print "-" * len(lc_area)
			methods = eval(lc_area).keys()
			methods.sort()
			count = 1
			for i in range(len(methods)):
				print form % methods[i],
				if count % numpline == 0 and i != len(methods)-1: print
				count += 1
			print
	else:
		command = command.split(" ")
		if len(command) == 2 and command[1] in METHODS.keys():
			if VARIABLES[PROGRAM] == True:
				x = obj2xml(METHODS[command[1]], command[1])
				print x.toxml()
				return

			print "%s" % command[1]
			for ptypes in [GETPARAMS, PARAMS]:
				if ptypes in METHODS[command[1]]:
					params = METHODS[command[1]][ptypes].keys()
					params.sort()
					for param in params:
						key = DEFAULT
						if EXAMPLE in METHODS[command[1]][ptypes][param].keys():
							key = EXAMPLE

						req = ""
						default = METHODS[command[1]][ptypes][param][DEFAULT]
						if default == None:
							req = "[Required]"

						if type(METHODS[command[1]][ptypes][param][key]) == types.ListType:
							for val in METHODS[command[1]][ptypes][param][key]:
								print "  %s=%s %s" % (param, val, req)
						else:
							print "  %s=%s %s" % (param, METHODS[command[1]][ptypes][param][key], req)
			print
		elif len(command) == 2 and get_camel(command[1].lower()) in INTERNAL.keys():
			if VARIABLES[PROGRAM] == True:
				x = obj2xml(INTERNAL[command[1].lower()], command[1].lower())
				print x.toxml()
				return

			for i in INTERNAL[get_camel(command[1].lower())]:
				print "%s" % i

def ifcond(cmd):
	cmd = shlex.split(cmd)

	if len(cmd) < 3:
		help("help if")
		print "\nRequire 2 or more arguments"
		return None

	condition = '"' + cmd[1] + '"'
	if "!=" in condition:
		condition = condition.replace("!=", '"!="')
	elif "=" in condition:
		condition = condition.replace("=", '"=="')
	condition = replvars(condition)
	if condition == "":
		return None

	ret = True
	if eval(condition):
		method = " ".join(cmd[2:])
		ret = process(method)

	return ret

def log(cmd):
	global LOGGER

	cmd = shlex.split(cmd)

	if LOGGER != None:
		LOGGER.close()
		LOGGER = None

	if len(cmd) == 2:
		LOGGER = Log(replvars(cmd[1]), "w")
	elif len(cmd) == 3:
		LOGGER = Log(replvars(cmd[1]), replvars(cmd[2]))
	elif len(cmd) > 3:
		help("help log")
		print "\nRequire at most 2 arguments"
		return None

	return True

def printcmd(cmd):
	cmd = cmd.split(" ", 1)

	if len(cmd) == 1:
		help("help print")
		print "\nRequire 1 or more arguments"
		return None

	out = replvars(cmd[1])

	print out

	return True

def report(cmd):
	global VARIABLES

	cmd = shlex.split(cmd)
	if len(cmd) != 2 and len(cmd) != 4:
		help("help report")
		print "\nRequire 1 or 3 arguments"
		return None

	# Which fields to display
	fields = replvars(cmd[1]).split(",")

	key = ""
	value = ""
	if len(cmd) == 4:
		if cmd[2].lower() != "where":
			help("help report")
			print "\nInvalid syntax for report"
			return None

		try:
			key, value = replvars(cmd[3]).split("=", 1)
		except:
			help("help report")
			print "\nInvalid syntax for report"
			return None

	# Expand *
	if "*" in fields:
		pos = fields.index("*")

		add = []
		for field in get_fields():
			if not field in fields:
				add.append(field)
		fields[pos:pos+1] = add

		try:
			while True:
				pos = fields.index("*")
				del fields[pos]
		except:
			pass

	# Add key to data field
	if key != "" and not key in fields:
		fields.append(key)

	# Count number of chunks in output
	chunks = 0
	if count("Count %s" % VAR_COUNT):
		chunks = VARIABLES[VAR_COUNT]
		del VARIABLES[VAR_COUNT]

	# Find data for all fields requested
	blank = []
	multiple = []
	data = {}
	widths = {}
	for field in fields:
		if findall("Findall \"%s\" %s" % (field, VAR_FIND)):
			data[field] = VARIABLES[VAR_FIND]
			del VARIABLES[VAR_FIND]
			del VARIABLES[VAR_PARENT]
			if len(data[field]) != chunks:
				print "Multi-value field '%s', skipping" % field
				blank.append(field)
				del data[field]
		else:
			blank.append(field)

	# Remove empty fields
	for field in blank:
		print "No data for field '%s', skipping" % field
		fields.remove(field)

	# Return if all blank
	if not len(fields) or (len(fields) == 1 and key in fields):
		return

	# Generator
	def consol(dict):
		for key in fields:
			yield dict[key]

	# Filter if requested
	if key != "":
		if not key in fields:
			# Invalid key field, remove
			key = ""
		else:
			i = 0
			while i < len(data[key]):
				if data[key][i] != value:
					for field in fields:
						del data[field][i]
				else:
					i += 1

	# Calculate column widths
	for field in fields:
		try:
			widest = len(max(data[field], key=len))
		except:
			widest = 0

		widths[field] = max([widest, len(field)])

	# Zip and sort
	data = zip(*consol(data))
	data.sort()

	# Print title
	print
	for field in fields:
		if field != key:
			print ("%%-%ds " % widths[field]) % field,
	print
	for field in fields:
		if field != key:
			print "-" * widths[field] + " ",
	print

	# Print data
	for line in data:
		if line == None: continue

		for i in range(len(fields)):
			if fields[i] != key:
				print ("%%-%ds " % widths[fields[i]]) % line[i],
		print
	print

	return True

def returncmd(cmd):
	global GOTO
	global RETURN

	try:
		GOTO = RETURN.pop()
	except:
		return False

	return True

def setvar(cmd):
	global PASS
	global VARIABLES
	global VERBOSE
	global VERBOSE_INIT

	cmd = cmd.split(" ", 1)
	if len(cmd) == 1:
		varis = VARIABLES.keys()
		varis.sort()
		for i in varis:
			if i != PASS:
				print "%s: %s" % (i, VARIABLES[i])
			else:
				print "%s: ******" % i
		return True

	cmd = cmd[1].split(" ", 1)
	if len(cmd) < 2:
		help("help set")
		print "\nRequire 0, 2 or 3 arguments"
		return None

	if cmd[0] in ["/A", "/a"]:
		cmd = cmd[1].split(" ", 1)
		if len(cmd) == 2:
			try:
				val = eval(replvars(cmd[1]))
				return setvar("Set %s %s" % (cmd[0], val))
			except:
				help("help set")
				print "\nError evaluating set expression"
				return None
		else:
			help("help set")
			print "\nRequire 0, 2 or 3 arguments"
			return None
	else:
		if cmd[0][:2] == "$_":
			print "Unable to set read-only internal variable %s" % cmd[0]
			return None

		if cmd[0] == "$IP":
			ipdata = checkipstr(cmd[1])
			if not ipdata[0]:
				print "Skipping malformed IP string in %s" % cmd[1]
				return True
			else:
				if ipdata[1] != None:
					VARIABLES[LOGIN] = replvars(ipdata[1])
				else:
					VARIABLES[LOGIN] = LOGINDEFAULT

				if ipdata[2] != None:
					VARIABLES[PASS] = replvars(ipdata[2])
				else:
					if ipdata[1] != None:
						VARIABLES[PASS] = getpass.getpass("Password for %s: " % cmd[1])

				if ipdata[3] != None:
					VARIABLES[IP] = replvars(ipdata[3])
		else:
			VARIABLES[cmd[0]] = replvars(cmd[1])

		if cmd[0] == VERBOSE:
			try:
				VARIABLES[VERBOSE] = int(VARIABLES[VERBOSE])
			except:
				print "Numeric value expected for $VERBOSE"
				VARIABLES[VERBOSE] = VERBOSE_INIT

		if cmd[0] == PROGRAM:
			if VARIABLES[PROGRAM] in ["True", "False"]:
				VARIABLES[PROGRAM] = eval(VARIABLES[PROGRAM])

				setvar("Set %s %s" % (VERBOSE, VERBOSE_WSMAN))
				setvar("Set %s %s" % (FORMAT, XML))
			else:
				print "Boolean value expected for $PROGRAM"
				VARIABLES[PROGRAM] = False

		if cmd[0] == PORT:
			try:
				VARIABLES[PORT] = int(VARIABLES[PORT])
			except:
				print "Numeric value expected for $PORT"
				VARIABLES[PORT] = PORTDEFAULT

	return True

def sleep(cmd):
	cmd = cmd.split(" ")
	if len(cmd) == 2:
		try:
			t = int(replvars(cmd[1]))
		except:
			help("help sleep")
			print "\nArgument 1 value not an integer: %s" % replvars(cmd[1])
			return None
	else:
		help("help sleep")
		print "\nRequire 1 argument"
		return None

	time.sleep(t)

	return True

def unsetvar(cmd):
	global REQ_VARIABLES
	global VARIABLES

	cmd = shlex.split(cmd)

	if len(cmd) != 2:
		help("help unset")
		print "\nRequire 1 argument"
		return None

	if cmd[1] in REQ_VARIABLES:
		print "Unable to unset required variable %s" % cmd[1]
		return None

	if not cmd[1] in VARIABLES.keys():
		return False

	del VARIABLES[cmd[1]]

	return True

def until(cmd):
	global OUTPUT
	global USLEEP
	global UTIMEOUT
	global VARIABLES
	global VAR_UNTIL
	global VERBOSE

	ret = True

	cmd = shlex.split(cmd)
	if len(cmd) < 3:
		help("help until")
		print "\nRequire 2 or more arguments"
		return None

	cond = replvars(cmd[1]).split("=")
	if len(cond) != 2:
		help("help until")
		print "\nInvalid argument 1 - format invalid"
		return None

	try:
		check = int(replvars(cmd[2]))
		total = int(replvars(cmd[3]))
		nexti = 4
	except:
		try:
			check = int(VARIABLES[USLEEP])
			total = int(VARIABLES[UTIMEOUT])
			nexti = 2
		except:
			help("help until")
			print "\nValue for $USLEEP or $UTIMEOUT not an integer"
			return None

	cmd = [quote_string(replvars(i)) for i in cmd]
	method = " ".join(cmd[nexti:])

	clock = time.clock()
	while True:
		if VARIABLES[VERBOSE] > VERBOSE_WSMAN:
			print "%s: %s" % (time.ctime(), method)
		run(method)
		if OUTPUT == "":
			ret = False
			break

		if find("Find %s=\"%s\" %s" % (cond[0], cond[1], VAR_UNTIL)):
			if not VAR_UNTIL in VARIABLES:
				ret = False
				break

			if VARIABLES[VAR_UNTIL] == cond[1]:
				break

		if VARIABLES[VERBOSE] > VERBOSE_WSMAN:
			print "  Until: %s != %s" % (cond[0], cond[1]),
			if VAR_UNTIL in VARIABLES.keys():
				print " [%s]\n" % VARIABLES[VAR_UNTIL]
				del VARIABLES[VAR_UNTIL]
			else:
				print

		time.sleep(check)

		if time.clock() - clock > total:
			print "Until: Timed out!"
			ret = False
			break

	if VAR_UNTIL in VARIABLES.keys():
		del VARIABLES[VAR_UNTIL]

	return ret

###
# Helpers

def getip():
	global IP
	global VARIABLES

	if IP in VARIABLES and VARIABLES[IP] != "":
		return VARIABLES[IP]
	else:
		print "IP of server undefined. --> Set $IP 10.0.0.1"
		return None

def quote_string(chunk):
	if chunk == None or not len(chunk):
		return chunk

	op = ""
	if chunk[0] in ['+', '/', '>', '?', '<', '{']:
		op = chunk[0]
		chunk = chunk[1:]
	elif chunk[:2] in ["//", ">>"]:
		op = chunk[:2]
		chunk = chunk[2:]

	nv = chunk.split("=", 1)
	if len(nv) > 1:
		for i in range(len(nv)):
			if " " in nv[i].strip(): nv[i] = '"%s"' % nv[i].strip()
		out = "=".join(nv)
	else:
		if " " in chunk:
			out = '"%s"' % chunk
		else:
			out = chunk

	return op + out

def replvars(cmd):
	global PASS
	global VARIABLES
	global VAR_DATE

	varis = VARIABLES.keys()
	varis.sort(reverse=True)
	for var in varis:
		if var == PASS:
			data = "******"
		else:
			data = VARIABLES[var].__str__()
		cmd = cmd.replace(var, data)

	cmd = cmd.replace(VAR_DATE, time.strftime("%Y%m%d%H%M%S"))
	cmd = re.sub("\$\w+", "", cmd)

	return cmd

def xmltoplain(obj, depth=''):
	offset = "  "
	out = ""
	for e in obj.childNodes:
		if e.nodeType == e.ELEMENT_NODE:
			if e.localName == "Selector":
				if e.hasAttributes():
					for attr in e.attributes.items():
						out += depth + attr[1]
			elif e.localName in ["Results", "Envelope", "Body", "PullResponse", "Items", "EnumerateResponse"]:
				offset = ""
			elif e.localName in ["Header", "EndOfSequence", "EnumerationContext"]:
				continue
			else:
				out += depth + e.localName.__str__()

			if e.firstChild != None and e.firstChild.nodeType == e.TEXT_NODE:
				data = e.firstChild.data.strip()
				if data != "":
					out += " = " + data

			out += "\n"

		out += xmltoplain(e, depth+offset)

		if depth == "" and e.nextSibling != None:
			out += "\n"
	return out

def securecmd(cmd):
	global PASS
	global VARIABLES

	if "-p" in cmd:
		repl = "-p"
		if "win" in sys.platform:
			repl += ":"
		else:
			repl += " "

		return cmd.replace(repl + VARIABLES[PASS], repl + "******")

	if "$IP" in cmd:
		ipstrre = re.findall("(.+):(.+)@(.+)", cmd)
		if ipstrre != None and len(ipstrre):
			pw = ipstrre[0][1]
			return cmd.replace(":%s@" % pw, ":******@")

	return cmd

def get_fields():
	x = OUTPUTXMLOBJ

	fields = []
	if x == None:
		return fields

	if x.childNodes == None or len(x.childNodes) == 0:
		return fields

	def recurse_fields(node):
		name = node.nodeName.encode("ascii").split(":")
		if len(name) == 2 and not "DCIM_" in name[1] and not name[1] in fields:
			fields.append(name[1])

		for node in node.childNodes:
			recurse_fields(node)

	for attr in x.childNodes[0].childNodes:
		recurse_fields(attr)

	return fields

def get_camel(str):
	if str == None:
		return str

	if len(str) == 1:
		return str.upper()

	return str[0].upper() + str[1:]

###
# Autocomplete, command history

def auto_complete(text, state):
	def ac_search(text, state, list, sep=""):
		for str in list:
			if str.lower().startswith(text.lower()):
				if not state:
					return str + sep
				else:
					state -= 1

		return None

	def ac_method(text, state):
		list = INTERNAL.keys()
		list.extend(METHODS.keys())
		list.sort()
		return ac_search(text, state, list, " ")

	def ac_fields(text, state, line):
		list = get_fields()
		if len(line) > 1:
			if line[-1] in list:
				return None
		return ac_search(text, state, list)

	def ac_params(text, state, method):
		list = []
		for i in [GETPARAMS, PARAMS]:
			if i in METHODS[method].keys():
				list.extend(METHODS[method][i].keys())
		return ac_search(text, state, list, "=")

	def ac_vars(text, state):
		list = VARIABLES.keys()
		str = ""
		if len(text):
			str = text[text.rindex("$"):]
		ret = ac_search(str, state, list)
		if ret != None and len(text):
			ret = text[:text.rindex("$")] + ret
		return ret

	def ac_expand(text, state):
		if not state:
			if text == "//":
				return "Context "
			elif text == "+":
				return "Count "
			elif text == "/":
				return "Find "
			elif text == "/*":
				return "Findall "
			elif text == ">>":
				return "Gosub "
			elif text == ">":
				return "Goto "
			elif text == "?":
				return "If "
			elif text == "<":
				return "Print "
			elif text == "<<":
				return "Report "
			elif text == "{":
				return "Until "

		return ""

	line = shlex.split(readline.get_line_buffer().encode("ascii"))

	try:
		if "$" in text:
			return ac_vars(text, state)
		elif len(line) == 0 or (len(line) == 1 and text != ""):
			str = ac_expand(text, state)
			if str != "":
				return str
			return ac_method(text, state)
		else:
			if text == "" or not re.match(".+?=.+?", line[-1]):
				if get_camel(line[0].lower()) in INTERNAL:
					cmd = line[0].lower()
					if "batch" == cmd:
						return None
					elif cmd in ["context", "find", "findall", "report"]:
						if len(line) < 3:
							str = ac_fields(text, state, line)
							if str != None:
								if cmd == "context":
									return str+"="
							return str
					elif cmd in ["set", "unset"]:
						if len(line) < 2:
							return ac_vars(text, state)
					elif "help" == cmd:
						return ac_method(text, state)
				elif line[0] in METHODS:
					return ac_params(text, state, line[0])
	except Exception, e:
		print e

	return None

try:
	readline.parse_and_bind("tab: complete")
	readline.set_completer(auto_complete)
	readline.set_completer_delims(" ,")
	readline.rl.mode.show_all_if_ambiguous = u"on"
	atexit.register(readline.write_history_file)
	readline.read_history_file()
except:
	pass

###
# IP helpers

def ip2num(ip):
	return struct.unpack('!L', socket.inet_aton(ip))[0]

def num2ip(n):
	return socket.inet_ntoa(struct.pack('!L', n))

def iprange2list(range):
	arange = range.split("-")
	if len(arange) != 2:
		return None

	ipdata = checkipstr(arange[0])
	if not ipdata[0]:
		return None
	ipdata2 = checkipstr(arange[1])
	if not ipdata2[0]:
		return None

	try:
		start = ip2num(ipdata[3])
		end = ip2num(arange[1])
	except:
		return None

	if start > end:
		return None

	ip = ""
	if ipdata[1]:
		if ipdata[2]:
			ip = "%s:%s@" % (ipdata[1], ipdata[2])
		else:
			ip = "%s@" % ipdata[1]

	ips = []
	while start <= end:
		ips.append("%s%s" % (ip, num2ip(start)))
		start += 1

	return ips

###
# Command line parsing


def checkip(ip):
	ipre = re.findall("^(\d+)\.(\d+)\.(\d+)\.(\d+)$", ip)
	if not len(ipre):
		return False

	return True

def checkhostname(hn):
	hnre = re.findall("^(?=.{1,255}$)[0-9A-Za-z](?:(?:[0-9A-Za-z]|\b-){0,61}[0-9A-Za-z])?(?:\.[0-9A-Za-z](?:(?:[0-9A-Za-z]|\b-){0,61}[0-9A-Za-z])?)*\.?$", hn)
	if not len(hnre):
		return False

	try:
		socket.getaddrinfo(hn, None)
	except:
		return False

	return True

def checkipstr(ipstr):
	ipstrre = re.findall("^(.+):(.+)@(.+)$", ipstr)
	if ipstrre != None and len(ipstrre):
		ipstrrepl = replvars(ipstrre[0][2])
		if checkip(ipstrrepl) == False and checkhostname(ipstrrepl) == False:
			return False, None, None, None

		return True, ipstrre[0][0], ipstrre[0][1], ipstrre[0][2]
	else:
		ipstrre = re.findall("^(.+)@(.+)$", ipstr)
		if ipstrre != None and len(ipstrre):
			ipstrrepl = replvars(ipstrre[0][1])
			if checkip(ipstrrepl) == False and checkhostname(ipstrrepl) == False:
				return False, None, None, None

			return True, ipstrre[0][0], None, ipstrre[0][1]
		else:
			ipstrrepl = replvars(ipstr)
			if checkip(ipstrrepl) == False and checkhostname(ipstrrepl) == False:
				return False, None, None, None

	return True, None, None, ipstr

def expandipfile(ips, filename=None):
	returnips = []
	for ip in ips:
		ip = ip.strip()
		if not len(ip): continue
		if ip[0] == "#": continue

		if os.path.isfile(ip):
			f = open(ip)
			lines = f.readlines()
			f.close()

			returnips.extend(expandipfile(lines, ip))
		else:
			ipdata = checkipstr(ip)
			if not ipdata[0]:
				if "-" in ip:
					range = iprange2list(ip)
					if range != None:
						for i in range:
							if not i in returnips:
								returnips.append(i)
					else:
						print "Skipped malformed IP range %s" % ip,
						if filename != None:
							print "in file %s" % filename
						else:
							print
				else:
					print "Skipping malformed IP string %s" % ip,
					if filename != None:
						print "in file %s" % filename
					else:
						print
			else:
				if not ip in returnips:
					returnips.append(ip)

	return returnips

def parseargs(cmdline=sys.argv):
	ips = []
	args = []
	wins = []
	cmds = []
	close = False
	parallel = 10
	quit = False
	silent = False

	ip = os.getenv("IP")
	if ip:
		if VARIABLES[IP] != "":
			ip = None

		for i in cmdline:
			if "IP=" == i[:3]:
				ip = None
	if ip:
		cmdline.append("IP=%s" % ip)

	for i in cmdline:
		if i == sys.argv[0]:
			continue

		elif i == "-c":
			close = True

		elif i == "-q":
			quit = True

		elif i[:2] == "-p":
			try:
				parallel = int(i[2:])
			except:
				print "Skipped non-integer value for -p"

		elif i == "-s":
			quit = True
			silent = True

		else:
			arg = re.findall("(.+?)=(.+)", i)
			if arg != None and len(arg) and not " " in arg[0][0] and arg[0][0][0] != "$":
				if "IP=" == i[:3]:
					ips = i[3:].split(",")
					ips = expandipfile(ips)
					if len(ips) == 1:
						args.insert(0, "IP="+ips[0])
						ips = []
				else:
					args.append(i)
			elif os.path.isfile(i):
				wins.append(i)
			else:
				cmds.append(i)

	if quit == True and not len(wins):
		cmds.append("quit")

	return [ips, args, wins, cmds, close, silent, parallel]

def loadargs(args):
	global VARIABLES
	global VERBOSE

	for arg in args:
		sarg = arg.split("=", 1)
		if len(sarg) == 2:
			s = "Set $%s %s" % (sarg[0], sarg[1])
			if VARIABLES[VERBOSE] > VERBOSE_WSMAN:
				print securecmd(s)
			setvar(s)
		else:
			print "Skipping malformed argument %s" % arg

###
# Execution

def pollprocs(procs, parallel=1):
	while len(procs) >= parallel:
		time.sleep(0.5)

		for ip in procs.keys():
			if procs[ip][0].poll() != None:
				if len(procs[ip]) > 1:
					procs[ip][1].close()
				del procs[ip]
				print "Completed for %s" % ip

def multiply(ips, args, wins, cmds, close=False, silent=False, parallel=10, delay=0):
	# Handle multiple IPs
	procs = {}
	for ip in ips:
		if "win" in sys.platform:
			if not silent:
				cexe = "%s\system32\cmd.exe" % os.getenv("WINDIR")
				cmd = [cexe, "/c", "start", "/wait", "%s IP=%s %s" % (os.path.basename(sys.argv[0]), ip, " ".join(args) + " ".join(cmds) + " ".join(wins)), cexe]
				if close == False:
					cmd.append("/k")
				else:
					cmd.append("/c")
			else:
				cmd = []
			if hasattr(sys, "frozen"):
				cmd.extend([sys.executable, "IP=%s" % ip])
			else:
				cmd.extend([sys.executable, sys.argv[0], "IP=%s" % ip])
		else:
			if not silent:
				cexe = "/usr/bin/xterm"
				cmd = [cexe, "-e"]
			else:
				cmd = []
			cmd.extend([sys.executable, sys.argv[0], "IP=%s" % ip])

		cmd.extend(args)
		cmd.extend(wins)
		cmd.extend(cmds)

		for i in range(len(cmd)):
			cmd[i] = cmd[i].replace('"', '\\"')
			if " " in cmd[i]:
				cmd[i] = '"' + cmd[i] + '"'
		cmd = " ".join(cmd)

		procs[ip] = []
		if not silent:
			proc = subprocess.Popen(cmd, shell=True)
		else:
			procs[ip].append(open("%s.log" % ip, "a"))
			procs[ip][0].seek(0, os.SEEK_END)
			proc = subprocess.Popen(cmd, shell=True, stdout=procs[ip][0], stderr=subprocess.STDOUT)

		print "Started for %s" % ip
		procs[ip].insert(0, proc)

		if delay:
			time.sleep(delay)

		pollprocs(procs, parallel)

	pollprocs(procs)

def run(inp):
	global FORMAT
	global INPUT
	global INPUTXML
	global OUTPUT
	global OUTPUTXML
	global OUTPUTXMLOBJ
	global LOGFILE
	global VARIABLES

	inputxml = ""
	output = ""
	outputxml = ""
	outputxmlobj = None
	cmd, method = buildcmd(inp)
	if cmd != None:
		try:
			if "win" in sys.platform:
				fname = cmd.split("file:")[1]
			else:
				fname = cmd.split("-J ")[1]
			fp = open(fname)
			inputxml = fp.read()
			fp.close()
		except:
			pass

		if VARIABLES[VERBOSE] > VERBOSE_QUIET:
			print securecmd(cmd) + "\n"
			if inputxml: print inputxml

		if TIMER in VARIABLES.keys() and VARIABLES[TIMER] == "True":
			start = time.time()
		pipe = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
		output = pipe.read()
		pipe.close()

		try:
			outputxml = output
			if re.search('<\?xml version=.*?>', outputxml) != None:
				outputxml = "<Results>" + re.sub('<\?xml version=.*?>', '', outputxml) + "</Results>"
			outputxml = ''.join([i.strip() for i in outputxml.split("\n")])
			outputxmlobj = xml.dom.minidom.parseString(outputxml)
			output = xmltoplain(outputxmlobj)
			output = re.sub("\n\n+", "\n\n", output).strip()
			if output != "":
				output = output + "\n\n"
		except:
			pass

		if output != "":
			if VARIABLES[VERBOSE] > VERBOSE_QUIET:
				if VARIABLES[FORMAT] == NORMAL:
					print output,
				elif VARIABLES[FORMAT] == XML:
					print outputxml + "\n"
				elif VARIABLES[FORMAT] == PRETTY:
					print toprettyxml(outputxmlobj)
				else:
					print "Unknown value for $FORMAT. Supported = normal, xml, prettyxml"

		if LOGFILE != None:
			fp = open(LOGFILE, "a+")
			fp.write("%s\n%s\n%s\n\n" % (securecmd(cmd), inputxml, outputxml))
			fp.close()

		if TIMER in VARIABLES.keys() and VARIABLES[TIMER] == "True":
			print "TIMER: %s - %d msecs\n" % (method, (time.time() - start) * 1000)

	INPUT = cmd
	INPUTXML = inputxml
	OUTPUT = output
	OUTPUTXML = outputxml
	OUTPUTXMLOBJ = outputxmlobj

def runmethod(cmd):
	global OUTPUT

	ops = []
	met = []
	acmd = shlex.split(cmd)
	for i in range(len(acmd)):
		if acmd[i][0] in ['+', '/', '>', '?', '<', '{'] or acmd[i][:2] in ["//", ">>"]:
			ops.append(quote_string(acmd[i]))
		else:
			met.append(acmd[i])

	j = 0
	grops = []
	for i in range(len(ops)):
		if ops[i][0] == '?' or ops[i][:2] == "//":
			grops.append(ops[i])
		else:
			try:
				grops[j] += " " + ops[i]
			except:
				grops.append(ops[i])
			j += 1

	ran = False
	cmd = " ".join([quote_string(replvars(i)) for i in met])
	if len(grops):
		for op in grops:
			if op[0] == '{':
				ret = process("%s %s" % (op, cmd))
				if ret == False:
					return ret
				ran = True

			if ran == False:
				run(cmd)
				if OUTPUT == "":
					return False
				ran = True

			if op[0] in ['+', '/', '>', '<', '?'] or op[:2] in ["//", ">>"]:
				ret = process(op)
				if ret == False:
					return False
	else:
		run(cmd)
		if OUTPUT == "":
			return False

	return True

def process(cmd):
	ign = ""
	cmd = cmd.strip().encode("ascii")
	if cmd == "" or cmd[0] in ["#", ":"]:
		return True
	elif cmd[0] == "-":
		ign = "-"
		cmd = cmd[1:]

	fcmd = cmd
	acmd = shlex.split(cmd)
	if len(acmd) == 1:
		if os.path.isfile(cmd) and (cmd[-4:] == ".win" or cmd[-3:] == ".py"):
			fcmd = "Batch " + cmd.replace("\\", "\\\\")
		elif cmd[0] == "+":
			fcmd = "Count " + cmd[1:]
		elif cmd[:2] == "//":
			help("help context")
			print "\nRequire 2 or more arguments"
			return False
		elif cmd[0] == "/":
			i = 1
			proc = "Find"
			if cmd[i] == "*":
				proc = "Findall"
				i+=1
			if cmd[i] == "$":
				findstr = re.findall("\$(.+)=(.+)", cmd[i:])
				if findstr != None and len(findstr):
					if " " in findstr[0][1]:
						fcmd = "%s \"%s\" $%s" % (proc, findstr[0][1], findstr[0][0])
					else:
						fcmd = "%s %s $%s" % (proc, findstr[0][1], findstr[0][0])
				else:
					fcmd = proc
			elif i == 1:
				fcmd = "Find " + cmd[1:]
			else:
				help("help findall")
				print "\nIncorrect syntax"
				return False
		elif cmd[:2] == ">>":
			fcmd = "Gosub %s" % cmd[2:]
		elif cmd[0] == ">":
			fcmd = "Goto %s" % cmd[1:]
		elif cmd[0] == "<":
			if cmd[1] == "<":
				fcmd = "Report %s" % cmd[2:]
			else:
				fcmd = "Print %s" % cmd[1:]
		elif cmd[0] == "$":
			setstr = re.findall("\$(.+?)(:?)=(.+)", acmd[0])
			if setstr != None and len(setstr):
				eqn = ""
				if setstr[0][1] == ":":
					eqn = "/a "
				fcmd = "Set %s$%s %s" % (eqn, setstr[0][0], setstr[0][2])
			elif cmd == "$":
				fcmd = "Set"
			else:
				help("help set")
				print "\nSet syntax error"
				return False
		elif cmd[:2] == "~$":
			fcmd = "Unset %s" % cmd[1:]
	else:
		if cmd[0] == "$":
			help("help set")
			print "\nSet syntax error"
			return False
		elif cmd[0] == "?":
			fcmd = "If %s" % cmd[1:]
		elif cmd[0] == "<":
			if cmd[1] == "<":
				if len(acmd[1]) < 5 or acmd[1][0:2] != "//":
					help("help report")
					print "\nReport syntax error"
					return False
				fcmd = "Report %s where %s" % (acmd[0][2:], acmd[1][2:])
			else:
				fcmd = "Print %s" % cmd[1:]
		elif cmd[:2] == "//":
			fcmd = "Context %s" % cmd[2:]
		elif cmd[0] == "{":
			fcmd = "Until %s" % cmd[1:]

	return full_process(ign+fcmd)

def full_process(cmd):
	global VARIABLES
	global VAR_LINE
	global VAR_UNTIL
	global VERBOSE

	ret = True
	ignoreRet = False

	if cmd[0] == "-":
		cmd = cmd[1:]
		ignoreRet = True

	if VARIABLES[VERBOSE] > VERBOSE_WSMAN:
		print "%s: %s" % (time.ctime(), securecmd(cmd).replace("\\\\", "\\"))

	lcmd = cmd.lower().split(" ")[0]
	if "quit" == lcmd or "exit" == lcmd:
		ret = None
		return ret
	elif "batch" == lcmd:
		ret = batchrun(cmd)
	elif "clear" == lcmd:
		if "win" in sys.platform:
			os.system("cls")
		else:
			os.system("clear")
	elif "context" == lcmd:
		ret = context(cmd)
	elif "count" == lcmd:
		ret = count(cmd)
	elif "find" == lcmd:
		ret = find(cmd)
	elif "findall" == lcmd:
		ret = findall(cmd)
	elif "gosub" == lcmd:
		ret = gosub(cmd)
	elif "goto" == lcmd:
		ret = goto(cmd)
	elif "if" == lcmd:
		ret = ifcond(cmd)
	elif "help" == lcmd:
		help(cmd)
	elif "log" == lcmd:
		ret = log(cmd)
	elif "print" == lcmd:
		ret = printcmd(cmd)
	elif "report" == lcmd:
		ret = report(cmd)
	elif "return" == lcmd:
		ret = returncmd(cmd)
	elif "set" == lcmd:
		ret = setvar(cmd)
	elif "sleep" == lcmd:
		ret = sleep(cmd)
	elif "until" == lcmd:
		ret = until(cmd)
	elif "unset" == lcmd:
		ret = unsetvar(cmd)
	else:
		ret = runmethod(cmd)

	if ignoreRet == True:
		ret = True

	method = cmd.split(" ")[0]
	method = get_camel(method)

	if ret == None:
		ret = False
	elif ret == False:
		if VAR_BATCHFILE in VARIABLES: print "%s:" % VARIABLES[VAR_BATCHFILE],
		if VAR_LINE in VARIABLES: print "\b%d -" % VARIABLES[VAR_LINE],
		if VERBOSE in VARIABLES and VARIABLES[VERBOSE] > VERBOSE_QUIET: print "%s failed" % method.replace("\\\\", "\\")
	elif ret:
		ret = True

	return ret

def batch(fname, cmds="", sub=None):
	global GOTO
	global BATCH
	global VARIABLES
	global VAR_BATCHFILE
	global VAR_LINE

	ret = True

	toline = fname.rsplit(":", 1)
	if len(toline) == 2:
		try:
			line = int(toline[1])
			fname = toline[0]
		except:
			line = None
	else:
		line = None

	if cmds == "":
		try:
			cmds = open(fname).readlines()
		except:
			print "No such file: %s" % fname
			return None
	else:
		cmds = cmds.split("\n")

	cmds = [cmd.strip("\r\n") for cmd in cmds]

	if VAR_BATCHFILE in VARIABLES:
		caller = VARIABLES[VAR_BATCHFILE]
	else:
		caller = None
	VARIABLES[VAR_BATCHFILE] = fname

	if ".py" == fname[-3:]:
		for i in range(len(cmds)):
			command = cmds[i].split()
			if len(command) and len(command[0]):
				if command[0][0] == "-": command[0] = command[0][1:]
				if command[0] in METHODS or command[0].lower() in PYRECITE:
					cmds[i] = cmds[i].replace(cmds[i].strip(), "if not process('%s'): sys.exit()" % cmds[i].strip())
				else:
					cmds[i] = re.sub("(\$[a-zA-Z0-9]+)", r"VARIABLES['\1']", cmds[i])

		exec("\n".join(cmds), globals(), globals())
	else:
		BATCH.append(cmds)

		if VAR_LINE in VARIABLES:
			callerline = VARIABLES[VAR_LINE]
		else:
			callerline = None

		if line == None:
			VARIABLES[VAR_LINE] = 0
		else:
			VARIABLES[VAR_LINE] = len(cmds)
			ret = goto("Goto %s" % line, sub)
			if ret == False or ret == None:
				return ret

			if GOTO != None:
				VARIABLES[VAR_LINE] = GOTO
				GOTO = None

		while VARIABLES[VAR_LINE] < len(cmds):
			ret = process(cmds[VARIABLES[VAR_LINE]].replace("\\", "\\\\"))
			if ret == False or ret == None:
				break

			if GOTO != None:
				VARIABLES[VAR_LINE] = GOTO
				GOTO = None
			else:
				VARIABLES[VAR_LINE] += 1

		if callerline != None:
			VARIABLES[VAR_LINE] = callerline
		else:
			del VARIABLES[VAR_LINE]

		del BATCH[-1]

	if caller != None:
		VARIABLES[VAR_BATCHFILE] = caller
	else:
		del VARIABLES[VAR_BATCHFILE]

	return ret

def interactive():
	ret = True
	while True:
		cmd = raw_input("--> ")
		cmd = cmd.replace("\\", "\\\\")
		ret = process(cmd)
		if ret == None:
			break

	return ret

def go(cmdline=sys.argv):
	global CONTEXT_START
	global CONTEXT_END
	global TEMPFILES
	global VARIABLES
	global VERBOSE

	CONTEXT_START = 0
	CONTEXT_END = -1

	wins = []
	ret = True
	try:
		# Parse arguments
		[ips, args, wins, cmds, close, silent, parallel] = parseargs(cmdline)

		if len(ips) > 1:
			# Multiply since multiple IPs specified
			try:
				multiply(ips, args, wins, cmds, close, silent, parallel)
			except KeyboardInterrupt:
				sys.exit()
		else:
			loadargs(args)
			ret = True
			for cmd in cmds:
				ret = process(cmd)
				if ret == None:
					break

			if ret == True:
				if not len(wins):
					# Interactive mode
					ret = interactive()
				else:
					for win in wins:
						ret = batch(win)
						if ret != True:
							break
	except KeyboardInterrupt:
		# Restart interactive mode if CTRL-C
		if not len(wins):
			ret = "Loop"

	# Delete all temp files created
	for fname in TEMPFILES:
		if VARIABLES[VERBOSE] > VERBOSE_WSMAN:
			print "Deleting %s" % fname
		os.unlink(fname)
	TEMPFILES = []

	# Stop any logging
	log("Log")

	return ret

###
# API

def get_verbosity():
	global VARIABLES
	global VERBOSE

	return VARIABLES[VERBOSE]

def set_verbosity(value):
	global VARIABLES
	global VERBOSE

	if type(value) == types.IntType:
		VARIABLES[VERBOSE] = value
		return True
	else:
		return False

def get_input():
	global INPUT

	return INPUT

def get_inputxml():
	global INPUTXML

	return INPUTXML

def get_output():
	global OUTPUT

	return OUTPUT

def get_outputxml():
	global OUTPUTXML

	return OUTPUTXML

def get_outputxmlobj(exit=True):
	global OUTPUT
	global OUTPUTXML
	global OUTPUTXMLOBJ

	if OUTPUTXMLOBJ != None:
		return OUTPUTXMLOBJ

	try:
		OUTPUTXMLOBJ = xml.dom.minidom.parseString(OUTPUTXML)
	except:
		if exit:
			print "Failed\n\n----- ERROR -----\n%s\n-----------------" % OUTPUT
			sys.exit()
		else:
			OUTPUTXMLOBJ = None

	return OUTPUTXMLOBJ

def get_curr_scriptpath():
	if VAR_BATCHFILE in VARIABLES:
		return VARIABLES[VAR_BATCHFILE]
	else:
		return ""

def set_logfile(filename=None):
	global LOGFILE

	if filename:
		LOGFILE = filename
	else:
		LOGFILE = None

if __name__ == "__main__":
	while True:
		ret = go()
		if ret != "Loop":
			break
