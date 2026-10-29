# Changelog

All notable changes to this project will be documented in this file.

## [2.5.0] - 2026-10-29
- The REST API requires an API key from the variable named in Apikeyenv. Added Allowremote and Alloworigins (CORS is no longer open to every origin). The certificate password comes from the variable named in Webserverpasswordenv. Fixed the extension name so the REST API callbacks resolve.

## [2.4.0] - 2026-10-27
- Added Macro REST API

## [2.3.1] - 2026-09-23
- Removed logging of errors and general log from macro data stored on disk.

## [2.3.0] - 2026-08-28
- Renamed widget folder `mc` to `am` and widget `MCLog` to `AMLog`
- Removed debug prints from MacroList `list1_callbacks`
- MacroList `onHover`/`onDrop` now return the extension's value instead of discarding it and always returning `True`

## [2.2.5] - 2026-06-09
- Updated changelog and version paths

## [2.2.3] - 2026-04-28
- Fixed Path Reference

## [2.2.2] - 2026-04-14
- Macro list refresh on color change

## [2.2.1] - 2026-04-02
- Add toggle to reload data on start

## [2.2.0] - 2026-04-02
- Add better checking for file updates

## [2.1.0] - 2026-04-02
- Add new color system to macro list

## [2.0.3] - 2026-03-26
- Add selects for version manager

## [2.0.0] - 2026-03-19
- Add version control system