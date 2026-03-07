![](seagulls.jpg)

This gets random sections from a stream video.

Each section is of variable duration.

Then it joins them into a single video.

You can use the `HUGE_URL` env var.

You can use the `HUGE_NAME` env var.

The name can be ommitted to use a random one.

`--open` can be used to open the file when ready.

## Installation

### Automatic (Recommended)

You can simply use `pipx`:

`pipx install git+https://github.com/madprops/hugegull --force`

### Manual

git clone this somewhere.

Make a shell alias:

`alias hgg="python ~/code/hugegull/main.py"`

## Configuration

Edit `~/.config/hugegull/hugegull.conf`

It is empty but you can make it look like this:

```
path = "/home/memphis/toilet"
duration = 45
fps = 30
crf = 30
```

## Usage

`hgg https://something.m3u8`

Local, YouTube, and Twitch video urls work as well.

Or:

```
export HUGE_URL="https://something.m3u8"
hgg
```