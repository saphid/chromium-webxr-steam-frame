# Patches

Local changes applied on top of the Chromium release that `build/build.sh`
builds (`CHROMIUM_VERSION`), in file-name order.

- `0001-xr-sandbox-allow-getsockopt-SO_PEERCRED.patch`: lets the XR process
  call `getsockopt(SOL_SOCKET, SO_PEERCRED)`, which SteamVR's OpenXR runtime
  needs. See [docs/technical-notes.md](../docs/technical-notes.md).
- `0002-v4l2-stateful-decoder-hevc.patch`: lets Chromium's stateful V4L2
  decoder (the kind the Frame has) decode HEVC, which upstream refuses with
  `kUnsupportedCodec`. It also requests larger input buffers above 4K,
  skips the P010 output format, which Chromium can't lay out yet, and
  reports a decode error, instead of crashing or stalling, when a frame
  doesn't fit or the output can't be set up. And it stops offering HEVC
  Main 10 and VP9 profile 2 from such decoders: the Frame's gives 10-bit
  output only in a compressed Qualcomm format Chromium can't use. See [docs/technical-notes.md](../docs/technical-notes.md#video-decoding).

- `0003-v4l2-stateful-coded-size.patch`: supplies the known coded dimensions
  when configuring the compressed-input queue. Iris accepts a zero-sized
  format but then rejects buffer allocation with `EINVAL`.

These patches modify Chromium source and are under
[Chromium's BSD-style license](https://chromium.googlesource.com/chromium/src/+/main/LICENSE),
Copyright The Chromium Authors.
