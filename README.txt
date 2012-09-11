Purpose
-------

The goal of Recite is to provide a simple and fast interface for the Dell Lifecycle
Controller API. It has an interactive mode that is useful to run one off commands
against a server as well as batch mode to allow automating a sequence of operations.

Getting Recite
--------------

Recite is provided as a standalone Python script. A Windows executable that bundles the
required Python environment is also available.

Requirements
------------

Client:
  Python version 2.4, 2.5 or 2.6
  Windows XP or greater with Windows Remote Management (winrm)
  Linux with Web Services for Management client (wsmancli)
    Builds available here: https://build.opensuse.org/package/show?package=wsmancli&project=systemsmanagement%3Awbem

Server:
  Dell 11G servers
    iDRAC Enterprise 1.70 (racks and towers), 3.21 (blades) or greater
    Dell Lifecycle Controller 1.5 or greater

  Dell 12G servers

Documentation
-------------

This README document goes over many of the features and capabilities of Recite. An
introductory presentation that describes Recite is also available.

Features

- Simple and consistent interface to generate WS-MAN commands
- Report generation with simple filtering
- Tab completion assistance in interactive mode
  - Expansion of available methods, shortcuts and declared variables
  - Contextual completion of properties returned in WS-MAN output
- Minimal scripting environment to create simple workflows
  - Find content in WS-MAN returned data
  - Variable support to store and reuse data
  - Support for simple logic, looping and sleeps
  - Script file support to batch commands
- Usable as a Python module with a simple API

Getting Started
---------------

Following are some typical commands to get started using Recite and the LC remote API.

Basic Inventory

Set target machine IP
> set $IP 10.0.0.1
> set $IP idrac.dell.com

Get system information
> GetSystemViews

Get firmware levels
> GetSoftwareIdentities

Get all BIOS attributes
> GetBIOSEnumerations
> GetBIOSStrings
> GetBIOSIntegers

Get NIC details
> GetNICViews
> GetNICEnumerations
> GetNICStrings
> GetNICIntegers

Get RAID details
> GetControllerViews
> GetVirtualDiskViews
> GetPhysicalDiskViews
> GetRAIDEnumerations
> GetRAIDStrings
> GetRAIDIntegers

Job Queue
> GetLifecycleJobs
 
Executing a job
 
Get value NumLock
> GetBIOSEnumeration InstanceID=BIOS.Setup.1-1:NumLock

Set to new value (if On, set to Off and vice versa)
> SetBIOSAttribute Target=BIOS.Setup.1-1 AttributeName=NumLock AttributeValue=Off

Create a job to execute
> CreateBIOSConfigJob Target=BIOS.Setup.1-1 RebootJobType=1

Save job ID just returned
> Find InstanceID $jid

Poll job ID for completion
> Until JobStatus=Completed GetLifecycleJob InstanceID=$jid

Show new value of NumLock
> GetBIOSEnumeration InstanceID=BIOS.Setup.1-1:NumLock

Command line
------------

python recite.py [NAME1=VALUE1 NAME2=VALUE2] ["CMD1" "CMD2" ...] [batch1.win batch2.win] [FLAGS]
  Set variable $NAME1 to VALUE1, $NAME2 to VALUE2 ...
  Execute CMD1, CMD2 in order ...
  Execute batch scripts in order and exit ...
  Enter interactive mode if no scripts specified
  Flags:
    -q  = exit after executing all commands

    When multiple IPs specified:-
    -c  = close instance foreground windows on exit
    -pX = maximum parallel instances at a time (default: 10)
    -s  = run instances silently, output appended to $IP.log

python recite.py IP=10.0.0.1,10.0.0.2,idrac.dell.com
  Spawn three instances of Recite in separate windows, each with IP specified

python recite.py IP=username:password@10.0.0.1
  Set $IP, $LOGIN and $PASS with a single assignment

python recite.py IP=username@10.0.0.1
  Set $IP and $LOGIN and prompt for password on commandline for security purposes

python recite.py IP=username:password@10.0.0.1,username@idrac.dell.com
  Spawn two intances with specfied $IP, $LOGIN and $PASS, prompt for password in latter

python recite.py IP=10.0.0.1-10.0.0.5,username@10.0.0.6-10.0.0.11
  Specify IP ranges on commandline

python recite.py IP=IP.ini
  Load IPs from file, one per line
  10.0.0.1, user:pass@10.0.0.1 or user@10.0.0.1
  10.0.0.1-10.0.0.5, user:pass@10.0.0.1-10.0.0.5, user@10.0.0.1-10.0.0.5
  idrac.dell.com, user:pass@idrac.dell.com or user@idrac.dell.com
  # comments a line

python recite.py IP=10.0.0.1 GetRSStatus GetLifecycleJobs
  Execute GetRSStatus and GetLifecycleJobs on specified IP

Commands
--------

Most of the API methods exposed by the Dell Lifecycle Controller WSMAN interface
are supported.

CQL, WQL and association filters can be used with -cql, -wql and -assoc flags. E.g.

  GetiDRACCardAttributes -cql="select * from DCIM_iDRACCardAttribute where 
    GroupDisplayName='iDRAC Users' and AttributeName='UserName'"

The script also provides a list of common internal commands to allow for minimal
programmatic functionality. These include:-

    Command     Shortcut
    -------     --------
    Batch
    Clear
    Context     //
    Count       +
    Find        /
    Findall     /*
    Gosub       >>
    Goto        >
    If          ?
    Log
    Print       <
    Report      <<
    Return
    Set         $
    Sleep
    Unset       ~$
    Until       {

Use the help command in interactive mode to see further details on all available
commands and methods and the required syntax.

Apart from the syntax described in help, commands can also be concatenated on
methods. This allows for a cleaner syntax.

E.g.

  CreateRAIDConfigJob Target=$ctlr RebootJobType=3 {ReturnValue=4096 /$jid=InstanceID
    Perform Until loop
    On success, perform Find operation

  GetRSStatus {Status=Reloading {Status=Ready
    Perform Until looking for Status=Reloading
    Perform Until looking for Status=Ready

  GetLifecycleJobs +$njob ?$njob=1 >End
    Count number of jobs
    If only one job, Goto End

Script execution is terminated if:
- A command returns an error. E.g. Find, Context, etc.
- A method returns no data. E.g. GetPhysicalDiskViews when no disks are present.
- A command has a syntax error

In order to ignore such errors and resume execution, prepend command with a -.

For example:
-Find InstanceID $id
-GetPhysicalDiskViews

Variables
---------

Settable variables

The following variables are loaded from environment variables if available. If
not, they are default initialized as specified.

$FORMAT
WS-MAN output is formatted as specified. Default: "normal"
  Set $FORMAT xml
  Set $FORMAT prettyxml

$IP
IP or hostname of the iDRAC against which WS-MAN commands are to be executed. Default: ""
  Set $IP 10.0.0.1
  Set $IP idrac.dell.com
  Set $IP username:password@10.0.0.1
  Set $IP username@10.0.0.1

$LOGIN
iDRAC username with WS-MAN privileges. Default: username
  Set $LOGIN username

$PASS
iDRAC password. Default: password
  Set $PASS dell

$PORT
Port on the iDRAC against where WS-MAN service is listening. Default: 443 
  Set $PORT 4443

$PROGRAM
Set to True to use Recite interactively from an external program. Returns all
output in XML format for easy interop.
  Forces:
    $FORMAT = xml
	$VERBOSE = 1

$TIMER
If True, display time taken by WS-MAN command. Default: False
  Set $TIMER True

$USLEEP
Default sleep delay in seconds used by until commands between method invocations.
  Set $USLEEP 20

$UTIMEOUT
Default total delay in seconds used by until commands before giving up.
  Set $UTIMEOUT 900

$VERBOSE
Control level of output from Recite
  Set $VERBOSE x

  where x is:
    0: Quiet
	1: WS-MAN
	2: Full

Internal variables

$_BATCHFILE
Name of current batch file (including path) with \ and / replaced with _.

$_DATE
Current date and time in yyyymmddhhmmss format.

$_LOCALIP
IP of the local system where script is running.

$_LINE
Current line number in a batch script.

Interactive help
----------------

Following is the current list of functions currently supported by Recite. For
additional information on a specific command, type "help <function>".

--> help

INTERNAL METHODS
----------------
Batch                                    Clear
Context                                  Count
Exit                                     Find
Findall                                  Gosub
Goto                                     Help
If                                       Log
Print                                    Quit
Report                                   Return
Set                                      Sleep
Unset                                    Until

BACKUP RESTORE METHODS
----------------------
BackupImage                              RestoreImage

BIOS METHODS
------------
ChangePassword                           CreateBIOSConfigJob
DeletePendingBIOSConfiguration           GetBIOSEnumeration
GetBIOSEnumerations                      GetBIOSInteger
GetBIOSIntegers                          GetBIOSString
GetBIOSStrings                           SetBIOSAttribute
SetBIOSAttributes

BOOT METHODS
------------
ChangeBootOrderByInstanceID              ChangeBootSourceState
GetBootConfigSetting                     GetBootConfigSettings
GetBootSourceSetting                     GetBootSourceSettings

iDRAC METHODS
-------------
ApplyAttribute                           ApplyAttributes
CreateiDRACConfigJob                     DeletePendingiDRACConfiguration
GetiDRACCardAttributes                   GetiDRACCardEnumeration
GetiDRACCardEnumerations                 GetiDRACCardInteger
GetiDRACCardIntegers                     GetiDRACCardString
GetiDRACCardStrings                      GetiDRACCardView
GetiDRACCardViews                        SetiDRACAttribute
SetiDRACAttributes

EVENT FILTER METHODS
--------------------
GetEventFilterView                       GetEventFilterViews
SetEventFilterByCategory                 SetEventFilterByInstanceIDs

JOB METHODS
-----------
CreateRebootJob                          DeleteJobQueue
GetLifecycleJob                          GetLifecycleJobs
SetupJobQueue

LC METHODS
----------
ClearProvisioningServer                  CreateLCConfigJob
ExportFactoryConfiguration               ExportHWInventory
ExportLCLog                              GetLCEnumeration
GetLCEnumerations                        GetLCInteger
GetLCIntegers                            GetLCString
GetLCStrings                             GetRSStatus
GetRemoteServicesAPIStatus               InsertCommentInLCLog
ReInitiateDHS                            SetLCAttribute
SetLCAttributes

LICENSE METHODS
---------------
DeleteLicense                            ExportLicense
ExportLicenseByDevice                    ExportLicenseByDeviceToNetworkShare
ExportLicenseToNetworkShare              GetLicensableDevice
GetLicensableDevices                     GetLicense
GetLicenses                              ImportLicense
ImportLicenseFromNetworkShare            ReplaceLicense
ShowLicenseBits

NIC METHODS
-----------
CreateNICConfigJob                       DeletePendingNICConfiguration
GetNICAttributes                         GetNICCapabilities
GetNICCapability                         GetNICEnumeration
GetNICEnumerations                       GetNICInteger
GetNICIntegers                           GetNICStatistic
GetNICStatistics                         GetNICString
GetNICStrings                            GetNICView
GetNICViews                              SetNICAttribute
SetNICAttributes

OSD METHODS
-----------
BootToHD                                 BootToISOFromVFlash
BootToNetworkISO                         BootToPXE
ConnectNetworkISOImage                   ConnectRFSISOImage
DeleteISOFromVFlash                      DetachDrivers
DetachISOFromVFlash                      DetachISOImage
DisconnectNetworkISOImage                DisconnectRFSISOImage
DownloadISOToVFlash                      GetDriverPackInfo
GetHostMACInfo                           GetNetworkISOImageConnectionInfo
GetOSDConcreteJob                        GetOSDConcreteJobs
GetRFSISOImageConnectionInfo             SkipISOImageBoot
UnpackAndAttach                          UnpackAndShare

POWER METHODS
-------------
RequestPowerStateChange                  RequestStateChange

PROFILE METHODS
---------------
GetCIMRegisteredProfile                  GetCIMRegisteredProfiles
GetLCRegisteredProfile                   GetLCRegisteredProfiles

RAID METHODS
------------
AssignSpare                              CheckVDValues
ClearForeignConfig                       ConvertToNonRAID
ConvertToRAID                            CreateRAIDConfigJob
CreateVirtualDisk                        DeletePendingRAIDConfiguration
DeleteVirtualDisk                        EnableControllerEncryption
GetAvailableDisks                        GetControllerView
GetControllerViews                       GetDHSDisks
GetEnclosureView                         GetEnclosureViews
GetPhysicalDiskView                      GetPhysicalDiskViews
GetRAIDEnumeration                       GetRAIDEnumerations
GetRAIDInteger                           GetRAIDIntegers
GetRAIDLevels                            GetRAIDString
GetRAIDStrings                           GetVirtualDiskView
GetVirtualDiskViews                      LockVirtualDisk
ReKey                                    RemoveControllerKey
ResetConfig                              SetControllerKey
SetRAIDAttribute                         SetRAIDAttributes
UnassignSpare

RECORD LOG METHODS
------------------
GetLCLogEntries                          GetLCLogEntry
GetLCRecordLogCapabilities               GetLCRecordLogs
GetSystemEventLogCapabilities            GetSystemEventLogEntries
GetSystemEventLogs                       SetLCLogEntryComment

ROLE BASED AUTHORIZATION
------------------------
GetUsersAssignedCLPPrivileges            GetUsersAssignedLANPrivileges
GetUsersAssignedSerialOverLANPrivileges

SENSOR METHODS
--------------
GetSensorView                            GetSensorViews
SetSensorThreshold

SERVICE METHODS
---------------
GetAssociatedPowerManagementService      GetClass
GetEFConfigurationService                GetEPR
GetPowerManagementService

SYSTEM METHODS
--------------
CreateSystemConfigJob                    DeletePendingSystemConfiguration
GetCPUView                               GetCPUViews
GetComputerSystems                       GetFanView
GetFanViews                              GetMemoryView
GetMemoryViews                           GetPowerSupplyView
GetPowerSupplyViews                      GetSystemAttributes
GetSystemEnumeration                     GetSystemEnumerations
GetSystemInteger                         GetSystemIntegers
GetSystemString                          GetSystemStrings
GetSystemView                            GetSystemViews
GetVideoView                             GetVideoViews
SetSystemAttribute                       SetSystemAttributes

UPDATE METHODS
--------------
GetSoftwareIdentities                    GetSoftwareIdentity
InstallFromURI

VFLASH MANAGEMENT METHODS
-------------------------
AttachPartition                          CreatePartition
CreatePartitionUsingImage                DeletePartition
DetachPartition                          ExportDataFromPartition
FormatPartition                          GetVFlashPartitionViews
GetVFlashView                            GetVFlashViews
InitializeMedia                          ModifyPartition
VFlashStateChange

Python API
----------

Given Recite's limited programmatic capabilities, complex workflows that require
more power are better of written in Python. Using Recite as a library is fairly
simple. The code below demonstrates how to use Recite as a Python module.

	import recite

	# Get the current verbosity level
	print recite.get_verbosity()

	# Set the verbosity level
	recite.set_verbosity(0)

	# Set logfile to capture all WS-MAN data
	recite.set_logfile("filename.txt")

	# Set IP details
	if recite.process("Set $IP username:password@10.0.0.1"):
		print "Succeeded"

	# Execute a simple command
	if recite.process("GetRSStatus"):
		print "Succeeded"

	# Execute a script file
	if recite.batch(filepath):
		print "Succeeded"

	# Execute a list of commands
	commands = """
	  CreateBIOSConfigJob Target=BIOS.Setup.1-1 RebootJobType=3 {ReturnValue=4096 /$jid=InstanceID
	  GetLifecycleJob InstanceID=$jid {JobStatus=Completed
	  GetRSStatus {Status=Reloading {Status=Ready
	"""
	if recite.batch("workflow-name", commands):
		print "Succeeded"

	# Obtain the command line of the last WS-MAN command
	print recite.get_input()

	# Obtain the input XML of the last WS-MAN command (if applicable)
	print recite.get_inputxml()

	# Obtain the output of the last WS-MAN command
	print recite.get_output()

	# Obtain the XML output of the last WS-MAN command
	xml = recite.get_outputxml()

	# Obtain the XML object output of the last WS-MAN command
	xml = recite.get_outputxmlobj()

	# Get the full path to the script executing currently
	path = recite.get_curr_scriptpath()