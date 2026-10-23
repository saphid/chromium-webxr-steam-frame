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


def block_end(text, i):
    """Offset just past the {...} block opening at text[i]. Braces inside
    quoted strings (with backslash escapes) don't count."""
    depth, quoted = 0, False
    while i < len(text):
        c = text[i]
        if quoted:
            if c == '\\':
                i += 1
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    sys.exit(f'unbalanced braces in {TEMPLATE}')


def group_span(text, gid):
    """Start and end offsets of the top-level "group" block whose id is gid."""
    for m in re.finditer(r'^\t"group"\n\t\{\n\t\t"id"\t\t"(\d+)"\n', text, re.M):
        if m.group(1) == gid:
            return m.start(), block_end(text, text.index('{', m.start()))
    sys.exit(f'group {gid} not found in {TEMPLATE}')


def input_block(group, name):
    """The "name" entry of a group's inputs, with its leading tabs, or ''."""
    m = re.search(r'^\t\t\t"' + re.escape(name) + r'"\n\t\t\t\{', group, re.M)
    return group[m.start():block_end(group, group.index('{', m.start()))] + '\n' if m else ''


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
    # The right stick's group becomes a copy of the left stick's, keeping its
    # id and its own click (pressing the stick), which the left stick lacks.
    scroll = text[ls:le].replace(f'"id"\t\t"{left}"', f'"id"\t\t"{right}"', 1)
    rs, re_ = group_span(text, right)
    click = input_block(text[rs:re_], 'click')
    if click and not input_block(scroll, 'click'):
        m = re.search(r'^\t\t"inputs"\n\t\t\{', scroll, re.M)
        if not m:
            sys.exit(f'no inputs in the left stick group of {TEMPLATE}')
        end = block_end(scroll, scroll.index('{', m.start())) - 1  # its closing brace
        end = scroll.rindex('\n', 0, end) + 1  # start of that line
        scroll = scroll[:end] + click + scroll[end:]
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
