# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One person: the owner. They run the app on a private server on their home Wi-Fi and use it
from their own devices on that network. Typical jobs: converting a file to the format something
else needs, and shrinking files to fit an upload limit (under 500 KB, 1 MB or 5 MB, or a custom
size). There are no other audiences; the app is not offered to anyone else.

## Product Purpose

A self-hosted, all-in-one file converter: images, documents, slides, spreadsheets, PDFs, data
files, audio and video, plus combining images and PDFs into one PDF and splitting PDFs. It
replaces the free online converter sites for its owner. Success means a file goes in and the
right format, at or under the right size, comes out, without the file leaving the owner's
network.

## Positioning

Compared with online converter sites, every reason is true at once:

- **Privacy:** files stay on the owner's own server and are deleted after an hour; nothing goes
  to a third party.
- **Exact size targets:** the user names a size limit and the app hits it with the method that
  loses least for each file type, or says how close it got.
- **All in one place:** every format family and the PDF tools live in one interface with batch
  conversion.
- **No ads, no limits:** no sign-up, watermarks, daily caps or advertising.

## Operating Context

- Runs on a private server on the owner's home Wi-Fi via `fileconvert serve`
  (`--host 0.0.0.0` so other devices on the network can reach it), or with Docker.
- Reached only from the owner's devices on the same network; it is not exposed to the internet.
- Uses LibreOffice, Ghostscript and FFmpeg on the server for documents, PDF compression, and
  audio/video.

## Capabilities and Constraints

- Three tools: **Convert files** (batch, per-file output format, image options, size limit),
  **Combine into PDF**, **Split PDF** (every page, or picked pages as one PDF or one per group).
- Size limit presets: under 5 MB, under 1 MB, under 500 KB, plus a custom size (at least 10 KB).
- Uploads and results are deleted after an hour (`FC_JOB_TTL`); uploads are capped at 200 MB per
  request by default (`FC_MAX_UPLOAD_MB`).
- Single user on a trusted network: there are no accounts, sign-in, or multi-user features.
  Exposing it beyond the home network would need authentication first.
- Runs on Linux, macOS and Windows.
- **Undecided:** the product name. "File Converter" is a working placeholder.

## Evidence on Hand

None. This is a personal tool: there are no customers, testimonials, usage numbers or press,
and none should be invented.

## Product Principles

1. **The file never leaves the owner's network.** No feature may send files or file details to
   an outside service.
2. **Say what happened.** When a size limit can't be met or a conversion fails, state the real
   result and what to do next; never pretend a target was hit.
3. **Least loss first.** Prefer the method that keeps the most quality, and never quietly do
   something destructive (dropping animation, colour profiles, or data) without saying so.
4. **One place for every format.** New formats join the same tools and flow rather than
   becoming separate apps.
5. **No friction for one user.** No sign-ups, nags or steps that only make sense for a public
   service.
