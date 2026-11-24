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

The coded-dimension correction was initially a separate patch 0003; it is now
part of `0002-v4l2-stateful-decoder-hevc.patch`. Iris accepts a zero-sized
format but then rejects buffer allocation with `EINVAL`; the patch supplies
`config.coded_size()` before allocation. HEVC 1080p and 7680 × 3840 decoded
normally in the installed Chromium 157.0.8088.0 build. Folding the correction
keeps local build retries idempotent: it no longer changes context used to
recognize another patch as already applied. The resulting source is unchanged.
See [device results](../docs/technical-notes.md#video-decoding).

Local build retries recognize the current patch revision. If a checkout has
only an older revision of patch 0002, refresh the source before building.
In a builder-owned tree with no source edits to keep, remove the revision
marker and rerun `build/build.sh`:

```sh
rm "${CHROMIUM_XR_DIR:-$HOME/chromium-xr}/ref"
```

This forces a clean Chromium checkout and drops local source modifications;
the existing dependencies and build output are reused.

These patches modify Chromium source and are under
[Chromium's BSD-style license](https://chromium.googlesource.com/chromium/src/+/main/LICENSE),
Copyright The Chromium Authors.
