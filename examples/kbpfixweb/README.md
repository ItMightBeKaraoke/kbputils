KBP Fix web interface
=====================

This is a demo web UI written in Flask to diagnose and fix issues with .kbp files, leveraging kbputils. You can see a live version at https://itmightbekaraoke.com/kbpfix

If you want to run this locally, install the dependencies (optionally from a virtual environment)

    pip install -r requirements.txt

Then run in flask (note this method of running is only for local non-production use. To use in production, use a WSGI server, ideally with an HTTP reverse proxy in front of it).

    flask run

This code does not include cleanup of temporary files beyond what the user manually initiates. If you're running on \*nix, you can create a cron job/systemd timer that does something like this:

    find ./tmp ! -name .do_not_delete -mtime +1 -delete

On Windows it can probably be accomplished with some sort of scheduled task
