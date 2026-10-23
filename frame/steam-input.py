#!/usr/bin/env python3
"""Make a Steam Input layout for Chromium XR where both thumbsticks scroll.

Steam gives the Chromium XR shortcut its "Web Browser" layout
(controller_neptune_webbrowser.vdf). There the left stick scrolls (a d-pad
bound to the mouse wheel) but the right stick moves the mouse pointer, which
the laser already does. This builds a copy of Steam's own template with the
right stick set up like the left one, so either stick scrolls. It reads the
template from the local Steam install rather than shipping Valve's file.
Python stdlib only.

  steam-input.py make OUT_FILE
"""
import os, re, sys

TEMPLATE = os.path.expanduser(
    '~/.local/share/Steam/controller_base/templates/controller_neptune_webbrowser.vdf')
TITLE = 'Chromium XR'
DESCRIPTION = 'Web browsing: either thumbstick scrolls'


def group_span(text, gid):
    """Start and end offsets of the top-level "group" block whose id is gid."""
    for m in re.finditer(r'^\t"group"\n\t\{\n\t\t"id"\t\t"(\d+)"\n', text, re.M):
        if m.group(1) != gid:
            continue
        depth, i = 0, text.index('{', m.start())
        while True:
            c = text[i]
            depth += c == '{'
            depth -= c == '}'
            i += 1
            if depth == 0:
                return m.start(), i
    sys.exit(f'group {gid} not found in {TEMPLATE}')


def source_group(text, source):
    """Id of the group the Default preset binds to an active source."""
    m = re.search(r'"(\d+)"\t\t"' + re.escape(source) + r' active"', text)
    if not m:
        sys.exit(f'no active "{source}" group in {TEMPLATE}')
    return m.group(1)


def make(out):
    with open(TEMPLATE, encoding='utf-8', newline='') as f:
        text = f.read()
    # Steam's templates use CRLF; edit with LF and write the original back.
    newline = '\r\n' if '\r\n' in text else '\n'
    text = text.replace('\r\n', '\n')
    left = source_group(text, 'joystick')
    right = source_group(text, 'right_joystick')
    ls, le = group_span(text, left)
    if '"mode"\t\t"dpad"' not in text[ls:le] or 'mouse_wheel' not in text[ls:le]:
        sys.exit(f'the left stick in {TEMPLATE} no longer scrolls; not changing it')
    # The right stick's group becomes a copy of the left stick's, keeping its id.
    scroll = text[ls:le].replace(f'"id"\t\t"{left}"', f'"id"\t\t"{right}"', 1)
    rs, re_ = group_span(text, right)
    text = text[:rs] + scroll + text[re_:]
    text = re.sub(r'("Title"\s+)"[^"]*"', lambda m: m.group(1) + f'"{TITLE}"', text, count=1)
    text = re.sub(r'("Description"\s+)"[^"]*"', lambda m: m.group(1) + f'"{DESCRIPTION}"', text, count=1)
    tmp = out + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline=newline) as f:
        f.write(text)
    os.replace(tmp, out)
    print(out)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == 'make':
        make(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
