# FileTalk Introduction
Lion Kimbro
2021-09-08

FileTalk is a primitive but effective system for supporting local & remote configuration & communication by way of JSON files.

**FileTalk is vulnerable to race-conditions,** so care must be taken when using this system.

## The Main Idea

The central mechanism is reading and writing JSON files.  JSON files can be read from remote computers as well, but not written to.

The strategy of FileTalk is such:
* use a single JSON file as the "root" for the system
* from any JSON file, make other JSON files easily within reach
* an easy system for creating and reserving space for temporary files, so that a JSON file can be passed as the sole argument to starting another process
* an easy system for navigating the JSON files

## Example Configuration

There's only one file that you need, and that's `filetalk.py`.  I've not made an installer yet for it, but it's easy enough to download it, and put it somewhere reachable.

Then you need to create a file that is known as the `HOME` or `FILETALK` file.  I call it "`filetalk.json`", but you can call it anything you like.

Here's what my filetalk.json file looks like:

    {"NAME": "Lion's Main Computer 2021",
     "OS": "WIN10",
     "LOCATION": "Lion's Bedroom",
     "TMPDIR": "./tmp/",
     "EXECUTABLES": "./executables.json",
     
     "COLORS": "https://raw.githubusercontent.com/bahamas10/css-color-names/master/css-color-names.json",
     "SUPERHEROES": "https://mdn.github.io/learning-area/javascript/oojs/json/superheroes.json",
     "ARTICLES": "d:/repo/lions_internet_office/2021/discussions/2021_articles.json"
    }

### What's This All Mean?

So if you query it and ask, "What's the name of this computer?", you get "`Lion's Main Computer 2021`".

You can see some other configuration in there as well.  I've put a note about my OS, and where it is.  (It's in my bedroom.)

None of those values are strictly required, but the following one *is* important.  At least -- it's important to `filetalk.py`: that is, `TMPDIR`.

`filetalk.py` uses `TMPDIR` to locate where it's going to put temporary files.  (side note: It's worth understanding that -- these are not OS-dependent temporary files.  OS-dependent temporary files have a number of restrictions, especially with regards to communication between processes, that renders them unworkable.)

Note that the `TMPDIR` is expressed as a relative address.  "Relative to what?", you might ask.  I hope you ask.  Usually in programming languages, relative addresses are interpreted relative the processes current working directory.  That'd be a mistake here, because we're puddle-jumping from JSON file to JSON file.  **The relative address is always interpreted relative to the directory containing the JSON file that mentions the relative address.**

Now look at the next one -- `"EXECUTABLES"`.  Don't worry about what that means -- just notice that it references another JSON file.  This JSON file could be "jumped" to.  Note also that it's a relative address -- so it is living in the same directory as this file.

Absolute addresses work too, of course -- at the end of the list is "ARTICLES", and that's an exact, literal address, to another JSON file.

And then notice that there's `"COLORS"` and `"SUPERHEROES"`.  I have no idea if those links will work by the time you look at this article, but they do immediately.  They are links to JSON files that can be downloaded from the Internet.

### Installing the Example

So how do you set it up?

Easy.  Just find anywhere on your filesystem, and paste that file in.  Call it `filetalk.json`, or whatever you like.

And then however you do it, set an environment variable "FILETALK" that is set to that path.

Make sure that your shell environment has loaded the environment variable.  And now you can use `filetalk.py` with ease, and anything else made to use the FileTalk system, to read and write files to the system.

## Using FileTalk.py: Digging

After ensuring that you have the environment variable FILETALK set, and that there's a file at that position, create a folder where you're going to play, and copy in filetalk.py.

Then try the following:

    from filetalk import *

(Normally you won't be doing a `from filetalk import *`; that's just for the sake of ease while playing with it.  Normally, you'd do just `import filetalk`.)

Now do the simplest query imaginable:

    dig("")

When I run that, I get the following result back:

    {'NAME': "Lion's Main Computer 2021",
     'OS': 'WIN10',
      'LOCATION': "Lion's Bedroom",
      'TMPDIR': './tmp/',
      'EXECUTABLES': './executables.json',
      'COLORS': 'https://raw.githubusercontent.com/bahamas10/css-color-names/master/css-color-names.json',
      'SUPERHEROES': 'https://mdn.github.io/learning-area/javascript/oojs/json/superheroes.json',
      'ARTICLES': 'd:/repo/lions_internet_office/2021/discussions/2021_articles.json'}

Look familiar?  It just gave us back the FileTalk JSON.

OK, let's look at something a little more interesting:

    dig(">NAME")

It responds with:

    "Lion's Main Computer 2021"

Hey!  Try something!  Edit your file.  Change the name from "Lion's Main Computer 2021", to something more reflective of your time, person, location, preference.

Then execute the command again, exactly the same.

You get a different result!

By default, digging is non-caching.  Just something to be aware of.  I have a rudimentary caching mechanism at time-of-writing (2021-09-09), and I think I may implement more sophisticated caching mechanisms to come.  But I think that *non-caching* will likely always be default, because pre-mature optimization is generally not so great.

OK, now let's look at what happens when you want to hop from one JSON file to another JSON file.

    dig(">ARTICLES")

Hmm...  Not what we were wanting:

    'd:/repo/lions_internet_office/2021/discussions/2021_articles.json' 

It just looked at it like a string.

How do we say, "I actually want you to *GO* there?"

Like this:

    dig(">ARTICLES !")

Here's a portion of the result, because -- it's just too long:


    {'$SCHEMA': 'tag:lionkimbro@gmail.com,2021:schema:article-postings-list-v1',
     'ARTICLES': [{'$SCHEMA': 'tag:lionkimbro@gmail.com,2021:schema:article-posting-v1',
                   'AUTHOR': 'tag:lionkimbro@gmail.com,2021:person:lion',
                   ...

OK.  If you wanted to get into the ARTICLES within there specifically, ...

    dig(">ARTICLES ! >ARTICLES")

As it happens, that returns a LIST of articles.

Let's look at, say, the eigth article.  That's #7, because we count the first as #0.

    dig(">ARTICLES ! >ARTICLES #7")
 
 The carrot "`>`" indexes into dictionaries whereas the pound "`#`" indexes into lists.
 
    {'$SCHEMA': 'tag:lionkimbro@gmail.com,2021:schema:article-posting-v1',
     'AUTHOR': 'tag:lionkimbro@gmail.com,2021:person:lion',
     'HTML': 'https://github.com/LionKimbro/lions_internet_office/blob/main/2021/users/lion/entries/2021-09-08_update-communications-mechanisms.md',
     'POSTED': '2021-09-08',
     'RAW': 'https://raw.githubusercontent.com/LionKimbro/lions_internet_office/main/2021/users/lion/entries/2021-09-08_update-communications-mechanisms.md'}

OK!  I think you get the idea..?

This also works with data that is fetched from the Internet.

    dig(">SUPERHEROES ! >members #0 >name")

This returns:

    "Molecule Man"

More likely, you want something like:

    dig(">SUPERHEROES ! >members")

...which returns:

    [{'age': 29,
      'name': 'Molecule Man',
      'powers': ['Radiation resistance', 'Turning tiny', 'Radiation blast'],
      'secretIdentity': 'Dan Jukes'},
     {'age': 39,
      'name': 'Madame Uppercut',
      'powers': ['Million tonne punch', 'Damage resistance', 'Superhuman reflexes'],
      'secretIdentity': 'Jane Wilson'},
     {'age': 1000000,
      'name': 'Eternal Flame',
      'powers': ['Immortality',
                 'Heat Immunity',
                 'Inferno',
                 'Teleportation',
                 'Interdimensional travel'],
      'secretIdentity': 'Unknown'}]

That information was all pulled from the Internet.

Where is this all going?

The goal is kind of to make an "Internet of Data."  A silly name for it, because the Internet is already an Internet of Data.  But if more and more people publish data with links about where to get more information about data and such, then I think we will have much more interesting programs, because our computer programs will know so much more about the world.

I'm going to write more programs and articles about this, but getting the foundations for linked data down is the most important thing right now, it seems to me.

`dig(...)` is a nice function, but it presently has some issues.  If you want to switch back and forth between navigating with `dig("...")` strings, and performing more programmatic searching -- that's a little difficult presently.  I think I'm going to implement a more intelligent "cursing" system, in the relatively near future.  But `dig(...)` is not complicated, and it s not hard to extend it on your own.

## More FileTalk.py: Reading & Writing Files

If you want to create a JSON file, it has a simplified format:

    write("C:/Users/Lion/foo.json", {...})

That writes the object (whatever that dictionary is) at the filepath, in JSON.

If you don't care about the filepath, -- that this is disposable data, -- you can just do this:

    p = tmpfile({...})

That will create a temporary file with your JSON data in it, and give you the path to it.  (It'll remember that it's a temporary file, and when you call `clean()`, it'll be in the list of files to delete.)

Reading is just as simple:

    read("C:/Users/Lion/foo.json")

When using files for communication, it's often convenient to delete the file, just as soon as you've read it:

    readrm("C:/Users/Lion/foo.json")

## FileTalk.py: Calling Other Programs with JSON data

Now I also like to use JSON to pass arguments to another program.

Here's how you call another program, and pass it data via JSON:

    run("other_program.py", {"SENDER": "Lion Kimbro",
                             "MESSAGE": "Hello, world!"})

What happens here is that FILETALK locates the TMPDIR, creates a temporary file inside of it, puts the JSON for the argument in there, and then invokes `other_program.py` and passes it the path to the temporary file as an argument.

What if you want to get a result from that program?

Here's another example:

      p = next_tmpfile_path()
      run("calculate.py",
          {"WRITE_RESULT": p,
           "EXPR": [5, 9, "+"]})
      result = read(p)  # contains integer 14

That call to "`next_tmpfile_path()`" creates a unique temporary filename, but doesn't put anything there.  We pass that path to the program we're calling (which here, is called "`calculate.py`".)

When `calculate.py` calculates the result of the expression, it puts the result into the filepath we passed it via "`WRITE_RESULT`".

Then when we get back control from `calculate.py` (a blocking call,) we read that file and get the result.

You could also use `result = readrm(p)`, and that would automatically clean up the file after it was read.

But it's okay to leave it around, too -- filetalk.py retains a list of all of the temporary files it creates, and if you call `clean()`, it will delete them all.  Of course, if you never get around to calling `clean()`, you'll have a bunch of files left all over the place.  But they're temporary files for a reason -- just periodically clean out the temporary file directory, and you should be good.

*I recognize that this implementation is fairly sloppy.*  I have two things to say about that:
1. I'm mainly concerned with getting an idea out there, into the Noosphere.  I leave professionalism to others.
2. I *do* intend to improve this tool, and it should have the controls and improvements that you'd expect, after some period of time.

I'm mainly concerned with getting the main idea across right now, and a basic implemetation working.  This idea is so simple, and the code is so simple, that an intermediate level programmer with just a few years programming should be able to implement something like this in a day or two.  (See a section in an article on my programming philosophy, wherein I articulate that [there's no code nearly so reusable as a clearly expressed idea.](https://github.com/LionKimbro/lions_internet_office/blob/main/2021/users/lion/entries/2021-09-06_programming-philosophy.md#ideas))

## FileTalk.py: Being Called by Other Programs with JSON Data

Here's what the `calculate.py` code might look like:


    import filetalk
    
    args = filetalk.arg()
    S = []
    
    for cmd in args["EXPR"]:
        if cmd == "+":
            S.append(S.pop()+S.pop())
        else:
            S.append(cmd)
    
    filetalk.write(args["WRITE_RESULT"], S.pop())

The first important call is `filetalk.arg()`.  That reads the sole argument -- which is a path to a JSON file -- the temporary file that contains the arguments, you will recall.

Then it creates a stack (S), and implements a miniature Forth-like RPN interpreter.  It received `[5, 9, "+"]`, so it puts `5` on the stack, `9` on the stack, and then reads off the `"+"` command, adding the two items off the top of the stack, and positioning on top the result (`14`).

It pops the top off the stack (`14`), and writes that to a JSON file.  What JSON file?  The temporary space reserved by the calling program.

    filetalk.write(args["WRITE_RESULT"], S.pop())

And *that's it*.

It's remarkably simple IPC, and you get all the JSON benefits of having structured data and such.
 
 ## Summary
* FileTalk is a system for puddle-jumping across JSON files.
* A single environment variable, `FILETALK`, roots the system.
* `import filetalk` to use the Python module.
  * There's no reason you'd have to use Python, though -- it should be simple enough to program a similar library, in any language, that replicates the key ideas here.
* You can read via puddle-jumping.
	* `dig("...")`
		* `>KEY`  -- navigate through a dictionary key
		* `#index`  -- navigate through a list index
		* `!`  -- jump to the file pointed at here, whether local or remote
* You can write and read JSON files.
	* `write(p, {...})`
	* `p = tmpfile({...})`
	* `read(p)`
	* `readrm(p)`
* You can reserve spots for temporary files.
	* `next_tmpfile_path()`
* You can call other programs, passing them JSON data:
	* `run(exec_path, {...})`
* And you can access the JSON file argument used to call you:
	* `arg()`

That's it!
