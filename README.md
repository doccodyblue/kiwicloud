# KiwiCloud
KiwiCloud takes usage statistics into a sqlite db and creates tag-clouds as png

Statistics are taken from KiWi's /users json statistics. You have to be in KiWi's 
local network to get those data.

For now it's beta and not fully dynamic configurationwise. Please look at the code
and modify as you need. Feel free to contribute changes.

# Installation
### get from git
git clone https://github.com/doccodyblue/kiwicloud.git

## Run
cd to your kiwicloud directory  
```cd kiwicloud```

```python3 kiwicloud.py -s [serverurl] -p [serverport] -d [0|1]``` 

### Example
```python3 kiwicloud.py -s 192.168.1.2 -p 8073 -d 1``` 

It will generate 3 PNG files that you can use for your website. 
You will have to upload / copy them to your destination manually. 
I use an every 1 minute cron job that just copys *.png over to my webserver. 

If you want to start over new, just delete kiwicloud.db - it will be created blank on next run.

To run in background I use tmux like this:  
```tmux new-session -c /home/pi/kiwicloud -d -n KiwiCloud -s KiwiCloud \; send-keys "python3 kiwicloud.py" Enter```    

This actually opens a new tmux session, starts the python with kiwicloud. You can then list your tmux sessions with
```tmux ls```

and attach to the session with
```tmux a -t KiwiCloud```

<img width="607" alt="image" src="https://user-images.githubusercontent.com/20392230/182165529-331d5bde-17a2-4ec3-8d60-1bf26384c564.png">


In the terminal it looks like this: (can be run in background, i use tmux for that)
<img width="573" alt="image" src="https://user-images.githubusercontent.com/20392230/182165331-bb9acb94-64d0-4562-838d-bccd1af38623.png">
