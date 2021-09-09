"""filetalk  -- JSON based communications system

FileTalk is a primitive system for supporting local & remote
configuration & communication by way of JSON files.

FileTalk is NOT race-condition safe, so care must be taken when using
this system.


The purpose is to make the following things easy:
* inter-process communication via JSON-encoded publishing
* inter-process calling via JSON-encodable arguments
* inter-computer communication via JSON-encoded reading


FileTalk rests on a single root file called "filetalk.json".  It's
location is specified by a global environment variable, "FILETALK."
This environment variable must be assigned to the FULL PATH to
filetalk.json.

It is intended that all systems are configured via a network of files
rooted in filetalk.json.


The functionality within this module includes:
  - locating the FILETALK file
  - JSON file reading & writing
  - digging through the FILETALK file
  - calling executables
  - temporary file construction & deletion for IPC purposes
  - cleaning the system
"""

from pathlib import Path
import time
import random
import sys
import os
import subprocess
import json


FILETALK_JSON_PATH = Path(os.environ["FILETALK"]).resolve()
FILETALK_JSON_DIR = FILETALK_JSON_PATH.parent

HOME = json.load(open(FILETALK_JSON_PATH))

# read out basic, critical information
HOMENAME = HOME["NAME"]
HOMEOS = HOME["OS"]
HOMELOC = HOME["LOCATION"]

# used in temporary file creation
PID = os.getpid()  # process ID at start
starttime = "{0:x}".format(int(time.time())) # unix time at start (in hex)

SERIALNO = "SERIALNO"  # for numbering temporary files
g = {SERIALNO: 0}  # start counting at 0

tmpfiles = []  # a list of temporary files created so far


# pathlib.Path-tolerant JSON Encoder

class ExtendedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        else:
            json.JSONEncoder.default(obj)


# Primitive File Operations

exists = os.path.exists
rm = os.remove  # raises FileNotFounderror
listdir = os.listdir

def write(p, msg):
    json.dump(msg, open(p, "w"), cls=ExtendedJSONEncoder)

def read(p):
    return json.load(open(p))

def readrm(p):
    data = read(p)
    rm(p)
    return data


# Primitive Process Execution

def arg():
    return read(sys.argv[-1])

def run(fullpath, arg=None):
    """Execute a program that may receive JSON data as its sole argument.
    
    That is, the target program either receives NO arguments
    (arg=None), or it receives the path to a JSON file, which is a
    temporary file created via tmpfile(arg).
    
    If you wish to receive data from the target in response, pass a
    return file position via a call to next_tmpfile_path().
    
    Example:
      p = next_tmpfile_path()
      run("calculate.py",
          {"WRITE_RESULT": p,
           "EXPR": [5, 9, "+"]})
      result = read(p)  # contains integer 14
    """
    L = []
    if fullpath.endswith(".py"):
        L.append(sys.executable)
    L.append(str(fullpath))
    if arg is not None:
        argpath = tmpfile(arg)
        L.append(str(argpath))
    return_code = subprocess.Popen(L).wait()
    if arg is not None:
        argpath.unlink()  # delete the temporary file now


# Temporary File Creation

def serialno(): i = g[SERIALNO]; g[SERIALNO] += 1; return i

def next_tmpfile_path():
    """Create a temporary filepath Path, and return it."""
    filename = "{}_{}_{}.tmp".format(PID, starttime, serialno())
    p = dig(">TMPDIR p") / filename
    tmpfiles.append(p)
    return p

def tmpfile(data):
    p = next_tmpfile_path()
    write(p, data)
    return p

def clean():
    """Delete all the temporary files created and noted."""
    for p in tmpfiles:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    del tmpfiles[:]


# File Network Lookup

def read_from_url(url):
    import urllib.request
    fid = urllib.request.urlopen(url)
    return fid.read().decode("utf-8")

def dig(s, start=None):
    """Dig through dictionaries, looking up information.
    
    ex:
        s: ">MSGPATH >INFO ! >FOO >BAR"
    
    general use:
    >key  -- navigate into a specific dictionary key
    #i    -- navigate into a specific list index
    p     -- convert the string value to a fully resolved pathname
    !     -- open the file thus named, and read as JSON;
             if it starts with "http:" or "https:",
             issue a GET request and read as JSON
    
    special use  (reading specific files; reading from the web; JSON-izing)
    read  -- open the file thus named, and read as text (UTF-8 formatted)
    get   -- issue a GET request to the given URL, read as text (UTF-8)
    json  -- interpret string as JSON
    
    ex:
        s: ">COLORS get json >pink"

    (...where "COLORS" is set to
     "https://raw.githubusercontent.com/bahamas10/css-color-names/master/css-color-names.json"
     in FILETALK file.)
    
    Returns the last thing settled on, no matter the type.
    
    Normally, start=None, which means to start from the FILETALK file.
    
    However, there are three other ways to start a dig:
      1. dig("...", start="CACHED")  -- (does NOT freshly read FILETALK file)
      1. dig("...", start="<path to a JSON file>")
      2. dig("...", start=({...}, "basepath" (or None))
    
    If a dictionary is specifically provided (per method #2), the
      second value, a basepath, is supplied so that relative addresses
      can be interpreted.  If no relative addresses will be
      encountered, None is fine.
    """
    # 1. determine loc & base_path
    if start == None:
        loc = read(FILETALK_JSON_PATH)
        base_path = FILETALK_JSON_DIR
    elif start == "CACHED":
        loc = HOME
        base_path = FILETALK_JSON_DIR
    elif isinstance(start, str):
        loc = read(start)
        base_path = Path(start).parent
    elif isinstance(start, tuple) or isinstance(start, list):
        loc = start[0]
        base_path = Path(start[1])
    # 2. now proceed
    for cmd in s.split():
        if cmd.startswith(">"):
            loc = loc[cmd[1:]]
        elif cmd.startswith("#"):
            loc = loc[int(cmd[1:])]
        elif cmd == "p":
            loc = (base_path / Path(loc)).resolve()
        elif cmd == "!":
            if loc.startswith("http:") or loc.startswith("https:"):
                loc = json.loads(read_from_url(loc))
                base_path = None  # not in Kansas anymore
            else:
                p = (base_path / Path(loc)).resolve()
                loc = read(p)  # step into filepath presently named
                base_path = p.parent
        elif cmd == "read":
            p = (base_path / Path(loc)).resolve()
            loc = p.read_text("utf-8")
        elif cmd == "get":
            loc = read_from_url(loc)
            base_path = None  # not in Kansas anymore
        elif cmd == "json":
            loc = json.loads(loc)
    return loc


# Special Operations -- do NOT rely on these being here;
#                       they are for development purposes only

def reserved(s):
    if s == "RM*":
        p = dig(">TMPDIR p")
        for p2 in p.glob("*.tmp"):
            print("DELETING:", p2)
            p2.unlink()
    elif s == "DIR":
        subprocess.call(["explorer",
                         str(FILETALK_JSON_DIR)])

