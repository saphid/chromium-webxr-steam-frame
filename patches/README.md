# Patches

Local changes applied on top of the Chromium release that `build/build.sh`
builds (`CHROMIUM_VERSION`), in file-name order.

- `0001-xr-sandbox-allow-getsockopt-SO_PEERCRED.patch`: lets the XR process
  call `getsockopt(SOL_SOCKET, SO_PEERCRED)`, which SteamVR's OpenXR runtime
  needs. See [docs/technical-notes.md](../docs/technical-notes.md).
- `0002-v4l2-stateful-decoder-hevc.patch`: lets Chromium's stateful V4L2
  decoder (the kind the Frame has) decode HEVC, which upstream refuses with
  `kUnsupportedCodec`, and gives it larger input buffers above 4K so 8K
  keyframes fit. See [docs/technical-notes.md](../docs/technical-notes.md#video-decoding).

These patches modify Chromium source and are under
[Chromium's BSD-style license](https://chromium.googlesource.com/chromium/src/+/main/LICENSE),
Copyright The Chromium Authors.
