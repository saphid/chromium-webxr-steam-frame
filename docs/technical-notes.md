# Technical notes

What we found getting WebXR working on the Steam Frame, for anyone picking
this up or taking it upstream. Tested with Chromium 156.0.8071.0 (arm64),
SteamOS 0.3.0 (build 20260922.6101926) and SteamVR 2.17.10.

## Why stock Chromium on Linux has no immersive WebXR

Chromium 154 was the first release to compile OpenXR on Linux
(`enable_openxr` includes Linux). But
`content/services/isolated_xr_device/xr_runtime_provider.cc` only creates an
OpenXR device when `ENABLE_OPENXR && IS_WIN`. Nothing on Linux calls the
OpenXR code, so the linker drops it. Flathub's arm64 Chromium contains no
OpenXR loader code at all, and flags such as `--force-webxr-runtime=openxr`
can't bring it back.

Two Gerrit changes fill that gap. Both have merged, and the first release
with both is 157.0.8088.0 (Canary):

- [CL 8132979](https://chromium-review.googlesource.com/c/chromium/src/+/8132979)
  creates the OpenXR device on Linux, using the Vulkan graphics binding
  (`XR_KHR_vulkan_enable2`). `device::features::kOpenXR` stays off by
  default, so it needs `--enable-features=OpenXR`.
- [CL 8441736](https://chromium-review.googlesource.com/c/chromium/src/+/8441736)
  runs the XR device service in its own sandbox (`xr_compositing`, with the
  `XrProcessPolicy` seccomp policy and a file broker), instead of requiring
  `--no-sandbox`.

The notes below were written against patch set 44 of CL 8132979, before it
merged. Neither problem is fixed upstream yet: the merged XR seccomp policy
still refuses every `getsockopt`, and nothing changes how the broker answers
`/proc/self`.
[CL 8498995](https://chromium-review.googlesource.com/c/chromium/src/+/8498995),
also in 157.0.8088.0, lets the XR sandbox read a Flatpak's GPU drivers; it
matters for the Flathub Chromium, not for this build.

## The SO_PEERCRED crash

With both CLs, the XR utility process crashed inside `xrCreateInstance` on
system call 0xd1 (`getsockopt` on arm64). SteamVR's IPC client calls
`getsockopt(fd, SOL_SOCKET, SO_PEERCRED, …)` to check which process is on the
other end of its socket, and `XrProcessPolicy` refuses every `getsockopt`.
[`patches/0001-xr-sandbox-allow-getsockopt-SO_PEERCRED.patch`](../patches/0001-xr-sandbox-allow-getsockopt-SO_PEERCRED.patch)
allows exactly `SOL_SOCKET`/`SO_PEERCRED` and still returns `EPERM` for
everything else.

## Why the seccomp filter is still off

With the patch, `xrCreateInstance` gets further but fails with
`Unable to init path manager: VRInitError_Init_Internal`. SteamVR's client
reads `/proc/self/status` to find its own process ID. Inside the seccomp
sandbox, file opens go through Chrome's broker process, so `/proc/self` is
the broker's, and SteamVR registers the broker's PID instead of the XR
process's. Granting the broker `/proc/self` doesn't help, because the broker
can only answer for itself.

Fixing this properly needs a change in Chromium: for example, having the
broker client rewrite `/proc/self` to `/proc/<caller pid>`, or opening the
needed `/proc` files before the sandbox seals. Until then the launcher passes
`--disable-seccomp-filter-sandbox`. The namespace sandbox still works:
SteamOS allows unprivileged user namespaces, so the setuid `chrome_sandbox`
isn't needed.

## What a working session looks like

- The page's `isSessionSupported("immersive-vr")` resolves `true`.
- After the **Allow VR?** prompt, `requestSession("immersive-vr")` succeeds.
  The first frame has a viewer pose with 2 views and a 2880 × 1440 framebuffer
  (1440 × 1440 per eye).
- SteamVR's log (`~/.local/share/Steam/logs/vrserver.txt`) shows the app move
  from `VRApplication_OpenXRInstance` to `VRApplication_OpenXRScene`, followed
  by controller binding files being created for
  `system.generated.openxr.chromium 156.chrome`.
- If nobody is wearing the headset, SteamVR keeps it in standby: the session
  stays at `XR_SESSION_STATE_SYNCHRONIZED`, the page sees
  `visibilityState: "hidden"`, and only the first frame runs. Put the headset
  on to see it.

## Input and frame rate (2026-09-27)

Measured with a session that clears to red, with `hand-tracking` and
`local-floor` requested:

- **Frame rate:** 72 fps. Over 16.6 s the median frame interval was 13.9 ms,
  p99 14 ms and max 14 ms, with no frame longer than 1.5× the median.
  SteamVR's `vrcmd --stats` counted 2,940 submits, 4 dropped frames (all at
  startup) and 2 reprojected.
- **Controllers:** the right controller appears as a `tracked-pointer` input
  source with profiles `oculus-touch` and
  `generic-trigger-squeeze-thumbstick`, an `xr-standard` gamepad (7 buttons,
  4 axes), a grip space, and a 25-joint `hand`. Its target-ray and grip
  poses were available on every frame, and not emulated. A physical squeeze
  produced `squeezestart`/`squeeze` events and set button 1 as pressed.
- **Not covered:** trigger (`select`), thumbstick axes, face buttons, the left
  controller (not connected during the test) and bare-hand tracking.
- **Haptics:** `gamepad.hapticActuators` is empty, so pages can't vibrate
  the controllers.
- Requesting `hand-tracking` makes Chromium ask **Allow hand tracking?** in
  the browser panel before the session starts.

## Graphics

Chromium's GPU process uses ANGLE on OpenGL, which runs on zink over the
Turnip Vulkan driver (Adreno 750). Chromium's own Vulkan backend stays off;
that doesn't stop the session. The OpenXR runtime uses Vulkan.

## Video decoding

Most VR180 and 360 video on the web is HEVC (H.265). Chromium on Linux has
no software HEVC decoder; it decodes HEVC only on a hardware decoder. Without
one, an HEVC video plays its sound but shows no picture: the element raises
no error and `currentTime` advances, but `videoWidth` stays 0 and no frames
are decoded. `canPlayType()` and `MediaSource.isTypeSupported()` report
HEVC as unsupported, so players that check pick another format, but many VR sites
serve HEVC without checking.

Verified on 2026-10-23 (BUILD_ID 20261015.6141207) with the Chromium 156
build, which had no hardware decoder: H.264 (up to 5760 × 2880) and VP9
played with frames, while HEVC 1080p, HEVC Main 10 4K and HEVC 7680 × 3840
played sound with 0 decoded frames.

The Frame's decoder is Qualcomm's `iris` V4L2 driver at `/dev/video-dec0`
(`/dev/video22`), a stateful decoder for H.264, HEVC and VP9 from 128 × 128
up to 8192 × 8192. The Frame has no VA-API driver. Steam's own browser
(`steamwebhelper`) runs with `--enable-features=PlatformHEVCDecoderSupport,V4L2VideoDecode`,
so Valve uses this decoder too.

So the build sets `use_v4l2_codec = true` and `use_vaapi = false`, the same
pair as upstream's `linux-v4l2-codec-rel` try builder. On desktop Linux,
Chromium looks for V4L2 decoders at `/dev/video0` to `/dev/video255`.
Hardware decoding is off by default in a build without VA-API, so the
launcher adds `AcceleratedVideoDecoder` to `--enable-features`.

The flags alone aren't enough. The Frame's decoder is stateful (it parses
the bitstream itself), so Chromium uses `V4L2StatefulVideoDecoder`, the
decoder written for Qualcomm Chromebooks. At 157.0.8088.0, and on `main`
in October 2026, its `Decode()` returns `kUnsupportedCodec` for HEVC, even
though the device's HEVC profiles are listed as supported.
`patches/0002-v4l2-stateful-decoder-hevc.patch` handles HEVC the way the
decoder handles VP9: each `DecoderBuffer` goes to the driver as it is.
That works because `VideoDecoderPipeline` already converts HEVC to Annex B
(`needs_bitstream_conversion_`), and media playback hands over one whole
frame per buffer, which stateful drivers need. H.264 goes through a
reassembler instead, because some sources split its frames. The patch also:

- gives HEVC 16 input buffers, as H.264 has, and requests 16 MiB buffers
  above 4K (upstream requests 4 MiB above 1080p, and an 8K keyframe can be
  larger). The driver may still allocate less.
- fails the decode when a frame is larger than its input buffer. Upstream
  `CHECK`s the size, which crashes the GPU process.
- leaves single-plane P010 out of the output formats. Chromium can't lay it
  out yet: the first decoded 10-bit frame would fail a `CHECK`. The Frame's
  decoder also gives 10-bit HEVC as NV12 (8-bit).
- reports a decode error when the decoder can't set up its output (for
  example, no usable output format) or a frame doesn't fit, and fails later
  decodes until the player resets. The decoder reports errors only through
  its decode callbacks, so upstream left playback waiting silently in these
  cases. Verified 2026-10-23: the
  Frame's `ffmpeg -c:v hevc_v4l2m2m` decoded 8-bit 1080p and Main 10 4K HEVC
  test clips on `/dev/video-dec0` with no errors, outputting NV12.

- stops offering HEVC Main 10 and VP9 profile 2 from V4L2 decoders that
  take whole frames (stateful ones, like the Frame's). See below.

**Chromium's V4L2 path on this Frame, verified 2026-10-23.** Steam's own
Chromium, `cefsimple` from `~/.local/share/Steam/steamrtarm64` (CEF on
Chromium 126), ran the codec probe with
`--enable-features=PlatformHEVCDecoderSupport,V4L2VideoDecode`. Results:

| Clip | Result |
|---|---|
| HEVC 1920 × 1080 | 152 frames decoded |
| HEVC 7680 × 3840 | 113 frames in 3.8 s |
| H.264, VP9 | decoded |
| HEVC Main 10 3840 × 2160 | failed to decode (`Failed to pick an output format`) |

For 8-bit streams the driver offers Q08C, NV12 and NV21 as output. For
10-bit HEVC it offers only Q10C, Qualcomm's compressed 10-bit format, which
Chromium can't use. Asking it for NV12 anyway (`ffmpeg -c:v hevc_v4l2m2m`)
gives frames with the right shapes but wrong colours. So 10-bit HEVC can't
play on this decoder in Chromium.

Chromium 126 still said `canPlayType()` "probably" for HEVC Main 10. A
player that trusts that would pick 10-bit HEVC over an H.264 copy and show
nothing. So the patch stops offering HEVC Main 10, and players fall back.
VP9 profile 2 goes to Chromium's software VP9 decoder.

Our patched Chromium 157 hasn't been run on the Frame yet.

## Panels and the Steam library

The Frame's compositor (gamescope) gives every Steam app ID its own SteamVR
overlay, named `valve.steam.desktopgame.<appid>`, which appears as a panel in
the headset. A non-Steam shortcut gets an app ID like any game, so launching
Chromium XR from the library gives it a panel. `frame/steam-shortcut.py` adds
the shortcut through the Steam client's DevTools port (`127.0.0.1:8080`,
page `SharedJSContext`) with `SteamClient.Apps.AddShortcut`, so Steam doesn't
need restarting. (`steam steam://addnonsteamgame/<path>` adds nothing.)

Steam preloads its in-game overlay, `gameoverlayrenderer.so`, into everything
it launches through `LD_PRELOAD`. In Chromium it segfaults the zygote during
library initialisation. The GPU process then fails to launch
(`GPU process launch failed: error_code=1002`), and after a few tries
Chromium quits with `GPU process isn't usable. Goodbye.` about 30 seconds
after starting. The `chromium-xr` launcher removes the overlay from
`LD_PRELOAD` before starting Chromium, keeping anything else that was
preloaded.

## Debugging

- **Testing without wearing the headset.** In standby SteamVR keeps the
  session hidden. With `vrcmd` from `/opt/steamvr/bin/linuxarm64`:
  `vrcmd --set-settings-bool power.pauseCompositorOnStandby 0`,
  `vrcmd --set-settings-float power.turnOffScreensTimeout 3600`, then
  `vrcmd --handlewakeup`. The session becomes visible and renders at the
  headset's rate. If it stays `visible-blurred`, the Steam dashboard is open
  over it: run `SteamClient.OpenVR.VROverlay.HideDashboard()` in the Steam
  client's DevTools (`127.0.0.1:8080`, page `SharedJSContext`). Undo with
  `--set-settings-bool power.pauseCompositorOnStandby 1` and
  `--set-settings-float power.turnOffScreensTimeout 5`. (The bool setter
  reads `true` as false; use 1 and 0.) Verified 2026-09-27: a WebXR session
  clearing to red filled both eyes in SteamVR's stereo screenshot.
- If the headset is outside its playspace, SteamVR shows the passthrough
  camera wherever a page leaves transparent pixels.

- `chromium-xr --remote-debugging-port=9223 URL` opens DevTools on the Frame's
  loopback. It has no password, so close the browser when you're done. If a
  VPN such as userspace Tailscale forwards traffic to loopback, other devices
  can reach it.
- `chrome://gpu` and `chrome://webxr-internals` show the graphics setup and
  the XR runtime Chromium picked.
- SteamVR's logs are in `~/.local/share/Steam/logs/`. `vrserver.txt` shows
  the session starting and which app SteamVR bound it to.
