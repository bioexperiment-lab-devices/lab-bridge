# Changelog

## [0.20.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.20.0...v0.20.1) (2026-05-24)


### Bug Fixes

* **users:** preserve dotted usernames in users_database.yml ([#154](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/154)) ([83998bd](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/83998bd881fb552a9945855bbc552b4be31b2de7))

## [0.20.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.19.4...v0.20.0) (2026-05-24)


### Features

* **siteapp:** docs in-page TOC + DFS prev/next ([#151](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/151)) ([3b9f598](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/3b9f598c6a74147a57bbd5c898cc7ee5419c9382))


### Bug Fixes

* **siteapp:** docs sidebar — reset on re-entry + always expand active section ([#153](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/153)) ([e52549d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e52549dd2f78c735884fe2f702b385e8a4e20302))

## [0.19.4](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.19.3...v0.19.4) (2026-05-24)


### Bug Fixes

* **caddy:** restore JupyterLab rendering by un-deferring global CSP ([#149](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/149)) ([1e32128](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1e32128bc9d685abcb0b0c6cca21c4e0356bc9b9))

## [0.19.3](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.19.2...v0.19.3) (2026-05-24)


### Bug Fixes

* **ci:** complete grafana OIDC handshake before probing /grafana/api ([#147](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/147)) ([3c81a0c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/3c81a0c4faa5441ff2d836cc173936c024f07416))

## [0.19.2](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.19.1...v0.19.2) (2026-05-24)


### Bug Fixes

* **ci:** probe authenticated services with real session, not 302 ([#145](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/145)) ([0e4e49b](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0e4e49b44e2d3104859d071fe424313203d92a10))

## [0.19.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.19.0...v0.19.1) (2026-05-23)


### Bug Fixes

* **deploy:** accept 200 or 308 for /docs/ in CI health check ([#142](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/142)) ([a93b880](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a93b88033842b07ab14461a617015ecd5894ccb2))

## [0.19.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.18.0...v0.19.0) (2026-05-23)


### Features

* **siteapp:** convert docs home into Overview section, polish sidebar titles ([#138](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/138)) ([f5d5bf2](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/f5d5bf2cb119e846c56d0bac6515f28246fd5d0b))


### Bug Fixes

* **siteapp:** render childless top sections as folders + black active section label ([#141](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/141)) ([57530a1](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/57530a145deed63f320061c2fe42fab9c72d2c27))

## [0.18.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.17.0...v0.18.0) (2026-05-23)


### Features

* **siteapp:** collapsible, clickable docs sidebar sections ([#135](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/135)) ([cb196f9](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/cb196f97716308900fd003a90dcfaac099f5ede0))

## [0.17.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.16.4...v0.17.0) (2026-05-22)


### ⚠ BREAKING CHANGES

* **siteapp:** manifest-driven docs sidebar nav ([#128](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/128))

### Features

* **siteapp:** manifest-driven docs sidebar nav ([#128](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/128)) ([36cf679](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/36cf679909b8be609e67fdaf81bdf41f394fb859))


### Bug Fixes

* **siteapp:** accept all methods on /_errors/{403,404} (1.6 follow-up) ([#127](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/127)) ([75ac35f](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/75ac35f656cf6e076b4c3fa86f60d03ee1cee12b))

## [0.16.4](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.16.3...v0.16.4) (2026-05-22)


### Bug Fixes

* **security:** remediate 2026-05-22 audit — critical + high + medium + low vulnerable findings ([#125](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/125)) ([1513af7](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1513af7520aefdee3a9aca4d2ae9284b5c9c5eac))

## [0.16.3](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.16.2...v0.16.3) (2026-05-22)


### Bug Fixes

* **siteapp:** re-render mermaid diagrams on theme toggle ([#123](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/123)) ([ee58e38](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/ee58e3803ca8901cc2bedecd1c551bf7690533d8))

## [0.16.2](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.16.1...v0.16.2) (2026-05-22)


### Bug Fixes

* **siteapp:** light-theme variant for code blocks ([#121](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/121)) ([2f40e17](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/2f40e17560315a550f0f0b902bcbfff7ce6a1179))
* **siteapp:** render mermaid in the user's chosen theme ([#119](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/119)) ([96f797b](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/96f797bfe9adbcc7e61e57e9363842c7073c773c))

## [0.16.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.16.0...v0.16.1) (2026-05-22)


### Bug Fixes

* **siteapp:** align docs nav title, header height, dark-mode sign-in CTA ([#115](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/115)) ([831a264](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/831a2642bb73f874df2c74fa1b4b4e17cb538ffd))

## [0.16.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.15.0...v0.16.0) (2026-05-21)


### Features

* **ui:** center login, fix dark-theme contrast, lucide+simpleicons ([#112](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/112)) ([c66dc1e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c66dc1e40c5a901d8c510406534ba4366d6ebea8))

## [0.15.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.14.3...v0.15.0) (2026-05-21)


### Features

* **shell:** persist navbar expanded state, reserve layout space ([#113](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/113)) ([92f9019](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/92f9019837c6faf0e9a113211371602c32bf4e8c))
* **siteapp:** hide home lab status from anonymous visitors ([#111](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/111)) ([4fa391c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/4fa391cfea3068d81f68129dac3560414bb75b5c))


### Bug Fixes

* **siteapp:** expire grafana_session cookie at Path=/grafana (no trailing slash) ([#109](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/109)) ([adbe37c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/adbe37cb0b80b2f0b8de764eda9ea7bf4cb7ec6a))
* **siteapp:** styled 403/404 across all error paths, navbar on error pages ([#108](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/108)) ([3dbdd28](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/3dbdd284f2bbe7cc9c6d2f7c66d9e9bb54f2668a))

## [0.14.3](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.14.2...v0.14.3) (2026-05-21)


### Bug Fixes

* **authelia:** skip OIDC consent prompt for grafana client ([#106](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/106)) ([e46d91f](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e46d91f5a1d74b304fee010702b5c7e917eae6d1))
* **siteapp:** 404 fall-through, login state, navbar active on /login ([#104](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/104)) ([b9c8463](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/b9c8463e104e05b2ea0e1153f4b320a374f4f771))

## [0.14.2](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.14.1...v0.14.2) (2026-05-21)


### Bug Fixes

* **deploy:** guard against empty authelia users_database.yml ([#101](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/101)) ([dfebf4d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/dfebf4d23ec01b45b69d92503a3c6cca7dc2c46b))
* **siteapp:** normalize full-URL targetURL in firstfactor proxy ([#103](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/103)) ([0ed3675](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0ed3675e58837c7a794ce1eaa0b1449177529b55))

## [0.14.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.14.0...v0.14.1) (2026-05-21)


### Bug Fixes

* **deploy:** keep /grafana/api/health public so deploy probe passes ([#98](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/98)) ([4bec39e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/4bec39ec62104016e8d63bef16ed505aa21d809b))

## [0.14.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.13.3...v0.14.0) (2026-05-21)


### Features

* **siteapp:** auth UI redesign — login, 403/404, navbar, sign-out ([#97](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/97)) ([578fcfd](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/578fcfd6766812b846d9e885da4eb6d130f02efd))

## [0.13.3](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.13.2...v0.13.3) (2026-05-21)


### Bug Fixes

* **deploy:** restart Authelia so newly-added users take effect ([#95](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/95)) ([2e8a6eb](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/2e8a6eb219f418ad3025a1de1423df439cac6bb8))
* **platform:** gate Grafana behind forward_auth; tear down both sessions on logout ([#96](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/96)) ([dcf2fbc](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/dcf2fbc15453867f6cd36505b11b647d4f71043f))
* **secrets:** bootstrap-authelia reads image pin from pins.yaml ([#93](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/93)) ([7cb9696](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/7cb969647850eb618e59db84a7a5ecbf8d881a3c))

## [0.13.2](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.13.1...v0.13.2) (2026-05-21)


### Bug Fixes

* **deploy:** probe /auth/api/health and emit bootstrap hint ([#91](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/91)) ([5fca91b](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/5fca91b338769e9bbb21fe25cadd34e82101053a))

## [0.13.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.13.0...v0.13.1) (2026-05-21)


### Bug Fixes

* **deploy:** skip Authelia in stack-only CI deploys ([#88](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/88)) ([d830de9](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/d830de93f4634f6360a02b74f8e7aa41be1272ac))

## [0.13.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.12.7...v0.13.0) (2026-05-21)


### Features

* **platform:** unified Authelia auth with groups and custom login ([#86](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/86)) ([9ad856c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9ad856c54730a0b68a5783557eedbcd41c54ce9c))

## [0.12.7](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.12.6...v0.12.7) (2026-05-20)


### Bug Fixes

* **platform:** unblock Grafana panels stuck at zero data ([#84](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/84)) ([0a991dc](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0a991dc899ec70f0065e8e2631516b10d2e551a1))

## [0.12.6](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.12.5...v0.12.6) (2026-05-20)


### Bug Fixes

* **flasher:** keep platform nav rail flush with viewport top ([#82](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/82)) ([1dde337](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1dde337998a869770c020bff2ce2d268fa8e1ca5))

## [0.12.5](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.12.4...v0.12.5) (2026-05-19)


### Bug Fixes

* **platform:** home consistency + nav-item proportions + draggable bookmark ([#80](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/80)) ([9988567](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9988567e0a1aced173ae08139dc0ac28536b1de9))

## [0.12.4](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.12.3...v0.12.4) (2026-05-19)


### Bug Fixes

* **flasher:** respect saved theme on load + apply siteapp design polish ([#78](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/78)) ([3122b3d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/3122b3db0755d2c8b8bd4b53b04d946a89c84fe4))
* **siteapp:** keep platform nav rail flush with viewport top ([#77](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/77)) ([3cd80a4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/3cd80a4aab9699ac022ec58d8fe3bbf381b7a9c0))

## [0.12.3](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.12.2...v0.12.3) (2026-05-19)


### Bug Fixes

* **platform:** close design gaps in nav, header, and dark-mode accents ([#76](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/76)) ([75c693c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/75c693c86454c73ded3da4dcb1e3625974caa299))
* **siteapp:** rebuild docs page to match design handoff ([#74](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/74)) ([a29e3c9](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a29e3c9283f5acc7698059f7e14a787a041091e4))

## [0.12.2](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.12.1...v0.12.2) (2026-05-19)


### Bug Fixes

* **platform:** unbreak navbar mount + close UI gaps vs design handoff ([#72](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/72)) ([e7cfe9a](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e7cfe9ad54c8436d16258a219c3fa43dbccf0ec9))

## [0.12.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.12.0...v0.12.1) (2026-05-19)


### Bug Fixes

* **siteapp:** declare packaging as direct dep + repair deploy health probe ([#69](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/69)) ([9eee508](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9eee508bfcdc37fbed8a464102b60a34db52e881))

## [0.12.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.11.0...v0.12.0) (2026-05-19)


### Features

* **platform:** apply hi-fi UI redesign to navbar, Home, Download, and Docs ([#67](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/67)) ([56542a8](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/56542a8b04f2bcc492d6ed29745d507c88540ce0))

## [0.11.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.10.0...v0.11.0) (2026-05-18)


### Features

* **siteapp:** rename agent download to SerialHop-Setup-v{version}.exe ([#66](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/66)) ([2fdc7ff](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/2fdc7ffc7cf7722e54a4ce2aee7c7658633902be))


### Bug Fixes

* **deploy:** exclude prometheus_data/ from rsync --delete ([#64](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/64)) ([610aa7c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/610aa7ccd7d9e048ae33ab0c4a08d5fe7cbd5851))

## [0.10.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.9.0...v0.10.0) (2026-05-18)


### Features

* **platform:** swap host monitoring from Yandex Unified Agent to Prometheus + Grafana stack ([#62](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/62)) ([0332177](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0332177efdc4119fe3e92176dccc97c7b74c3c13))


### Bug Fixes

* **deploy:** restart grafana after rsync so provisioning changes apply ([#63](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/63)) ([c5eceed](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c5eceed9456735400529dfed47184fe71257ef3c))
* **unified-agent:** make container actually run + match real config schema ([#60](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/60)) ([b7cf3a8](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/b7cf3a85c3f3d5d7c968e1153f83962f03982a00))

## [0.9.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.8.2...v0.9.0) (2026-05-18)


### Features

* add Yandex Unified Agent for host monitoring ([#58](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/58)) ([6b72266](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6b72266744983967681f303b8c619019b49372d4))

## [0.8.2](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.8.1...v0.8.2) (2026-05-18)


### Bug Fixes

* **platform:** point navbar Grafana and Download Agent at real routes ([#56](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/56)) ([15ad68b](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/15ad68b891d1871ae1054815e0acb46fce2825a2))

## [0.8.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.8.0...v0.8.1) (2026-05-17)


### Bug Fixes

* **release:** cut 0.8.1 to publish missing lab-bridge-caddy image ([#54](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/54)) ([f5e6a0f](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/f5e6a0ffa868e89c3df9915cdf4a546bcaed4aac))

## [0.8.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.7.1...v0.8.0) (2026-05-17)


### Features

* **flasher:** tighten topbar, portal dropdowns, hash tag colors ([#45](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/45)) ([df0ea5d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/df0ea5d6e3e846e97c447fb23712cb8c1b035418))
* **flasher:** URL routing, persistent flash draft, cross-record links ([#46](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/46)) ([4eb790f](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/4eb790fd2b5a1bce4eafb2563f3b72193f731618))
* **platform:** shared navbar via Caddy injection ([#50](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/50)) ([f5ea897](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/f5ea897f579ddd24ebb545fcda93681c07fc5c92))


### Bug Fixes

* **flasher:** tolerate 404 from disconnect before flash ([#48](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/48)) ([46dd88d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/46dd88d3587a8f2573af1360405e9e67628e74e0))
* **flasher:** wrap logs table rows instead of horizontal scroll ([#49](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/49)) ([46ab92e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/46ab92eef91e53c09ac1925ae1661c792446087d))

## [0.7.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.7.0...v0.7.1) (2026-05-17)


### Bug Fixes

* **flasher:** map tags→tag_ids in PATCH firmware route ([#43](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/43)) ([0f265b5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0f265b577de0411f12b2d16601b7fa805bfd75a3))

## [0.7.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.6.1...v0.7.0) (2026-05-17)


### Features

* **flasher:** redesign web UI to match Flasher.html mockup ([#41](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/41)) ([68871a2](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/68871a2d9a3b4f0086fa0ba3073139ba991b6709))

## [0.6.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/platform-v0.6.0...platform-v0.6.1) (2026-05-17)


### Bug Fixes

* **ci:** strip release-please annotation when verifying platform VERSION ([#38](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/38)) ([c13b9e0](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c13b9e0266d35a227a9d38af1877f3eccc8e0e85))

## [0.6.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/platform-v0.5.0...platform-v0.6.0) (2026-05-17)


### Features

* **flasher:** document and test URL-encoded per-port disconnect ([#33](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/33)) ([3b8c1e6](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/3b8c1e610f30d023ca876c427a88173613f54ff7))


### Bug Fixes

* **ci:** release-please-rebase must actually rebase, not stack a commit ([#36](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/36)) ([aa33f77](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/aa33f7703b3354c78ba29f33083d423f68a49e10))

## [0.5.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/platform-v0.4.1...platform-v0.5.0) (2026-05-16)


### Features

* **flasher:** firmware library, history, tabs, bearer upload ([#25](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/25)) ([a140816](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a1408163ee45e623bfa03237754786a880a4e965))

## [0.4.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/platform-v0.4.0...platform-v0.4.1) (2026-05-16)


### Bug Fixes

* **ci:** deploy-public-docs rsyncs to /srv/lab-bridge, not ~/lab-bridge ([#23](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/23)) ([431c56c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/431c56c65ff5a97a174ee0bb21e91d55387cdd2a))

## [0.4.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/platform-v0.3.1...platform-v0.4.0) (2026-05-15)


### Features

* add config.example.yaml schema ([0fc2f0e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0fc2f0e76ac3c9439d8e14ec8fa8ab474f2cc3d4))
* add Taskfile skeleton and doctor task ([afe1b6d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/afe1b6d06670f8141446550b3b5cd7ef88d6c7b1))
* **auth:** replace Caddy basic_auth with JupyterLab password auth ([a6c6e3d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a6c6e3ded87016308d1ebea47a3c36857a37e0e4))
* **auth:** replace Caddy basic_auth with JupyterLab password auth ([1922ec0](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1922ec0b60ffe08787cbadb6d1bff72b815b0ca9))
* **caddy:** add /docs, /download, /admin (basic_auth), /api/agent/upload ([dcce76e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/dcce76eb073f88b8c1831c63ab8e2624908e41f4))
* **caddy:** proxy /api/public/* to siteapp ([dcc85fc](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/dcc85fc81bed025f44740474bbb7b0bfc22e5796))
* **caddy:** redirect / to /docs/ so root lands on the public docs portal ([9ac8394](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9ac839456593509751711a7d0c299b6ad79339b1))
* **caddy:** route /grafana/* to grafana:3000 subpath ([eb0b74d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/eb0b74dc3105a09e7c404071e3d9a8e2fe22ac99))
* **chisel:** authorize loki:3100 forward tunnel for every client ([2382be6](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/2382be6f9c169880c64a62ea3278ca2522617039))
* **compose:** add loki and grafana services to render pipeline ([36efb34](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/36efb3424a1aeea89ce82bcc1b2aaa32ed0ffa26))
* **compose:** mount siteapp clients.json and set SITEAPP_CLIENTS_FILE ([039787c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/039787c94dd6d74ef79789b30ceef2ad6b520114))
* **compose:** wire siteapp service + agent_upload_token secret ([b697be4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/b697be46b29fd065926b2c84e0893ebb2b31b759))
* **config:** add loki/grafana config sections and validation ([d9b3304](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/d9b33049a59ee5fd6ae45304fa1b0c7d738600fc))
* **config:** siteapp.image + admin_password_hash; render new __VARS__ ([e4cd8e5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e4cd8e5c6a43b0287445df74f293847cd0456984))
* **deploy:** add deploy.sh with render + rsync + compose up ([4dd1cbe](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/4dd1cbe514b27f56b873334d94e9dc8867e823fb))
* **deploy:** include /api/public/health in post-deploy health check ([56c3baf](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/56c3baf35d5e244bbd604fdfc9ee750dca22482a))
* **deploy:** preflight agent token + healthcheck /docs, /download, /admin (401) ([9bb532a](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9bb532ad98a6ea5577afb459ac4b684c6ce0e7b6))
* **deploy:** render siteapp/clients.json into the staging dir ([1a16907](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1a16907dc6c2f1aa66837a046221f5db1c75d1a5))
* **deploy:** stage loki config, grafana provisioning, admin password ([c6b1a69](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c6b1a6955ddf9360a137684c61630f69868db9f7))
* **docker:** set JupyterLab root directory in docker-compose template ([44bf207](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/44bf2079ef4f8f65cb6823ceb241557aa1d1ac8d))
* **flasher:** operator firmware-flashing UI ([#7](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/7)) ([04c109e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/04c109edcc8d095ff8c0573e018afbc49d5c3067))
* **flasher:** skip-backup switch, retry-with-filled-form, dark-theme palette ([#9](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/9)) ([976e293](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/976e2933e0090e11a2159d966f04b9f95ffab1b9))
* **grafana:** provision Loki datasource and Lab client logs dashboard ([6f59850](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6f59850e234830dcda63d9a505f7717366697c83))
* **lib:** add common.sh logging, errors, and SSH wrapper ([a0572ba](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a0572ba7f60550c0e06c4f7d00f2f6e3bc4120d1))
* **lib:** add config.sh with validation and load ([8fe2b37](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/8fe2b37827077d0208c7168d3392e3949c125a00))
* **lib:** add crypto.sh with gen_password and bcrypt_hash ([73b7de0](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/73b7de099ec95ce2abdaf03bcbea4e7533bf3382))
* **loki:** add filesystem-backed config template with retention substitution ([863c13d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/863c13d5a716950340f36057eb25527ac7841887))
* **ops:** add logs:loki, logs:grafana, loki-disk commands ([ac73cdf](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/ac73cdf56b8101d40328b1c8a0093109c5136cac))
* **ops:** add ps/logs/ssh/restart/down/destroy/backup tasks ([416bc94](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/416bc94faebf25956af33fcd93c25da56f8ed6c0))
* **ops:** logs:siteapp and site-disk task entries ([6f0e3c7](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6f0e3c7c56cf15d5a513d473bf257654bdbf89b2))
* **provision:** add provision.sh with Docker, ufw, and dirs ([bf2aaed](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/bf2aaed862d131ecf8d80fd0f6af4e7d3cd55e0d))
* **provision:** create loki_data and grafana_data with correct uids ([23252d5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/23252d5241f4f2c89b3dd5c50df2b8f44501d00c))
* **render:** emit siteapp clients.json from chisel_clients ([a3733d4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a3733d4a3267f46e8c660651641aac58c106d878))
* **render:** render Caddyfile with basic_auth from caddy_users ([6e000e8](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6e000e8e98fe70fd860dd94034d4f358c7a65c6c))
* **render:** render chisel users.json with route restrictions ([628c1dd](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/628c1dd458725d29073d75173bf4c4f6f4082c67))
* **render:** render docker-compose.yml from template ([3145292](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/3145292fde6cfb9b92f5e160a3359dfe38943906))
* **render:** siteapp clients.json emits {port, password_sha256} ([bf713a5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/bf713a533a5085be58524f11607fdcee5de773fc))
* **secrets:** add secrets:add-client task ([7613479](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/7613479119e7ce64441c4d29e5819cd63695551d))
* **secrets:** add secrets:add-user task ([351c819](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/351c8199aa1d445e7f6a7b2b7e8fb84c5dce5ced))
* **secrets:** add set-grafana-password task ([84dfd8d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/84dfd8d25e9fa6ed5b0fc4e416ed6c36a1c27e8e))
* **secrets:** add set-user-password and rm-user tasks ([340eecd](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/340eecd63363b91d199158add6132179ae8478f9))
* **secrets:** add show-client and rm-client tasks ([66783cb](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/66783cb4a73b9e997a7cb50fcf679c716b55f686))
* **secrets:** task secrets:rotate-agent-upload-token ([12e1fa4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/12e1fa489403179e69c3b08f8e044c52a2b17168))
* **secrets:** task secrets:set-admin-password (caddy hash-password) ([c6b2a52](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c6b2a52cf7b98843a7a1282e1aa859b92285e386))
* **siteapp:** /api/public/clients/{username} with bearer auth ([5228c2e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/5228c2ee6f254cbf8365ec07988ed6e30896e366))
* **siteapp:** /api/public/health proxies chisel server health ([b5b9bab](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/b5b9bab1595a662c47f858066aef428463beab35))
* **siteapp:** /api/public/server-info for agent bootstrap ([#3](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/3)) ([c0074e4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c0074e4432e3dc783a4ddbef7ee93b41cb80c695))
* **siteapp:** /download/agent page and binary stream ([64d0c3e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/64d0c3e4bd7b0c82ac91e6643cc948f529630cde))
* **siteapp:** add generic 4-pane window icon (CC0) ([b849147](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/b849147870b9b6d8882f583801eb85d4771268f9))
* **siteapp:** add load_roster for chisel client discovery ([5701054](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/57010540141518590ab8ee24ff2741a7e71eebd9))
* **siteapp:** add mermaid-init.js (lazy mermaid loader) ([6ad7be9](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6ad7be93c5907d76458cef06909d11b35dbe7465))
* **siteapp:** add SITEAPP_CLIENTS_FILE to Settings ([6f338d0](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6f338d08137a727b167ddcd7860e79872d61a6ca))
* **siteapp:** admin agent page (manual upload + rotate-token UI) ([09c9450](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/09c945015600948b3b8d65034c988179159abb10))
* **siteapp:** admin docs file manager (upload/delete/rename/new-folder) ([79db8e6](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/79db8e6b1c68bb27579a7c4c7f383b2538836ae2))
* **siteapp:** allow-list inline HTML via bleach (img, kbd, ...) ([a21af88](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a21af88287a4fa122bff08edc9c862e57086763a))
* **siteapp:** build_nav walks docs/ for sidebar tree ([263d213](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/263d2133e568f78e7dae5bc36fcda0e14433c476))
* **siteapp:** build-and-push helper for GHCR ([474b613](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/474b61313ee6c44458649c6ebcc4b994c3d68e3c))
* **siteapp:** Dockerfile (python:3.13-slim + uv frozen sync) ([d4c0490](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/d4c04909b7a40d5bb233cfa706fc4946e997f038))
* **siteapp:** FastAPI skeleton with /healthz and base template ([1eef621](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1eef621fdc67bd9838464b7b4b4889f5250a62e6))
* **siteapp:** GET /api/clients/ — discover chisel tunnel by username ([02c3830](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/02c3830f376a055420182350de0e09cc48af1919))
* **siteapp:** GET /api/clients/ returns chisel client roster ([aa54036](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/aa540362c14f0cb4d64d1e749e6b080a8bf9416c))
* **siteapp:** GitHub-style alert blockquotes ([!NOTE]/[!TIP]/...) ([e2e3e88](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e2e3e884294ab8336ab175e44b44d6dd0d370f07))
* **siteapp:** load mermaid bundle only on pages with diagrams ([0d284b6](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0d284b6aa5ffee1be03cc858f95af912bad636ed))
* **siteapp:** markdown renderer with pygments + anchors ([5876ab1](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/5876ab16b0538f9751e5ef0355dc090451ca7f49))
* **siteapp:** POST /api/agent/upload (bearer token, atomic write) ([44a8981](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/44a898155c585dfa59cfa15f340c08123fda41ec))
* **siteapp:** project scaffolding (uv + pytest + ruff) ([8d1e1c1](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/8d1e1c1f3c1d2a8c9bc4fbb2ef10a98c3d3be41b))
* **siteapp:** public /docs routes with EN/RU + trailing slash ([e83121e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e83121ee4736d0d21267f392e420b5c999f2aac3))
* **siteapp:** public client status & discovery routes ([3339a0c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/3339a0c743b373efdb54ee5498649b91eb7be54f))
* **siteapp:** public_clients helpers — roster load, bearer parse, verify ([0b82367](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0b8236763a1e231402444ab9756f31e8c7321704))
* **siteapp:** rebrand /download/agent as SerialHop ([0a19340](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0a19340414ce1a41f7d5eec9b924080c08494a32))
* **siteapp:** render mermaid blocks as &lt;pre class=mermaid&gt; + needs_mermaid flag ([ec1a818](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/ec1a818b56e619e04ce9eb2383534d31e3aebcdd))
* **siteapp:** rewrite default index.md as platform welcome page ([e6099b4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e6099b4bca7e57ad6dd716dd3f482cfbf420cff3))
* **siteapp:** sanitize_filename + safe_join helpers ([025ffbf](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/025ffbfaff6edc01ec3c5f579bafbd7b7b40ec0f))
* **siteapp:** seed default_docs/ recursively + richer landing page ([96d7dc2](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/96d7dc2a1f92079dbab4359a2ec1f827ddd2f7cc))
* **siteapp:** serve doc-relative images (svg/png/...) from /docs/ ([1e25e85](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1e25e85a6c1a79cc810b119bfd873ba17238cf51))
* **siteapp:** settings loader (SITE_DATA + token from env or *__FILE) ([44c1529](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/44c152964b2be5b7a416b0dc66ef772f974ff215))
* **siteapp:** TCP probe helper for chisel reverse port liveness ([c268808](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c2688083095312bea09be5dab40833bc3d9f76f5))
* **siteapp:** translation pairing (en/ru with fallback) ([017bf01](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/017bf01b8ea72b9b1dba0a2dbfae93148468b526))
* **siteapp:** vendor jupyter/grafana/github SVG icons ([8090264](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/809026404665c8d5e918c74149d64ca0a7de333e))
* **siteapp:** vendor mermaid.min.js (pinned 11.4.1) ([ac0450e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/ac0450eb22c2e9ae9d62e6820ce65ebbee692ea2))
* **siteapp:** warn about SmartScreen on agent download page ([d7dc9e0](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/d7dc9e00ed5359b1ce4cd5d8fc370695b2db995e))


### Bug Fixes

* align fake-VPS UIDs with production for jovyan bind-mount ([7f7f189](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/7f7f189fe6728f385138897fa91d62c5a51e12b5))
* **caddy:** add default_sni so IP-only TLS works for SNI-less clients ([c49f0a3](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c49f0a3ca91a57cfeeaebc5ccd4569e94e38a977))
* **caddy:** drop issuer internal — ACME-only, fail loud on issuance error ([f6567c7](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/f6567c7f3f4f98c7b298f7ef63cddf1ff5bdf7ad))
* **caddy:** preserve /grafana prefix on upstream so Grafana sub-path stops looping ([647afac](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/647afac9f6c4562edb6ba926dff3da3d05e7116a))
* **caddy:** route /_static/* to siteapp so templates load CSS/JS ([e7a7893](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e7a7893baf2c16a75528acfb0f7339f92045f0c4))
* **deploy:** also exclude caddy_config from rsync --delete ([fe8235f](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/fe8235f023cc64b57cfb25b56468f91c5bb4b7a3))
* **deploy:** ensure caddy and chisel restart on config changes ([9ae4dae](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9ae4dae90efd5a9a4096677dbf7999e577e3b498))
* **deploy:** probe /grafana/ in healthcheck so a crash-looping grafana/loki fails the deploy ([56ccde9](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/56ccde9c2d33e164884d3ca9f71fa765cf7b7ed7))
* **deploy:** restart caddy + drop tls-shorthand to match issuer block ([f770945](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/f7709456db128c98da1a75df66e9b806bdb3e303))
* **deploy:** stage grafana admin_password as 0644 so the container can read it ([9c04b99](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9c04b99cf9df7ae2d0958d06cf6663d91acc8d77))
* **flasher:** unstick result-view trap on refresh + safety-net runner exception ([#11](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/11)) ([4e94859](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/4e94859de13cb2c31fa057448a7afcfe68aef6d0))
* **grafana:** replace invalid max_over_time on log stream with count_over_time ([6529f47](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6529f479c88ab19163d3c7e8063b449a2a7fddb2))
* **render:** stop silencing yq errors in render_siteapp_clients ([9855b06](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9855b067de344119195a23e18f61f794e6c95a54))
* **secrets:** drop removed --plaintext-stdin flag from caddy hash-password ([679438f](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/679438f647d819b89d03774ef43a6b2566518013))
* **siteapp:** admin rename must keep an allowed file extension ([51f9568](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/51f95688422c7d306871e4eb9b3a83c0c777299c))
* **siteapp:** admin target sanitization, new-folder 4xx, jinja breadcrumb namespace ([47d6b64](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/47d6b64b14e188770aef397c48e44eafe502b4c8))
* **siteapp:** broaden upload_agent .part cleanup to all exceptions ([6ae53d2](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6ae53d2e4b87034c00c171d2a2d9f50542e40d56))
* **siteapp:** close /docs/..%2F traversal leak; tighten cookie flags ([9d5dfc6](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9d5dfc63ac5c6e259ab4c3a548d5a0c7e78c6982))
* **siteapp:** extract title from token tree; skip guess_lexer; +regression tests ([bc4afd5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/bc4afd5e4de26948b8dac32b09d9141a991f3dd1))
* **siteapp:** load mermaid as classic deferred scripts (UMD bundle, not ES module) ([071fed5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/071fed5741de1ce38c6fdb3e70610074b5b9c5e3))
* **siteapp:** preserve table alignment + footnote markup through bleach ([d378924](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/d378924a81247dbeb58c176670820d5515fcbac8))
* **siteapp:** seed default docs/index.md so fresh deploys pass healthcheck ([ffc2410](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/ffc241028cc2a43817a3233a01dabf22ce5f5d1c))
* **siteapp:** single &lt;pre&gt; per fenced code block ([5545c5f](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/5545c5f1152080627034a2f43f208f04d5c02132))
* **siteapp:** validate roster entry shape in _load_roster ([8944c30](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/8944c3000682618b49e3a97ab95d3886f94a5ecd))
* update valid_config fixture hash to 53 chars ([8db76cb](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/8db76cb187f51b3969d9b82a056811f30f69de8e))

## [0.3.1](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.3.0...v0.3.1) (2026-05-14)


### Bug Fixes

* **flasher:** unstick result-view trap on refresh + safety-net runner exception ([#11](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/11)) ([4e94859](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/4e94859de13cb2c31fa057448a7afcfe68aef6d0))

## [0.3.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.2.0...v0.3.0) (2026-05-13)


### Features

* **flasher:** skip-backup switch, retry-with-filled-form, dark-theme palette ([#9](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/9)) ([976e293](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/976e2933e0090e11a2159d966f04b9f95ffab1b9))

## [0.2.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.1.0...v0.2.0) (2026-05-13)


### Features

* **flasher:** operator firmware-flashing UI ([#7](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/7)) ([04c109e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/04c109edcc8d095ff8c0573e018afbc49d5c3067))

## [0.1.0](https://github.com/bioexperiment-lab-devices/lab-bridge/compare/v0.0.1...v0.1.0) (2026-05-12)


### Features

* add config.example.yaml schema ([0fc2f0e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0fc2f0e76ac3c9439d8e14ec8fa8ab474f2cc3d4))
* add Taskfile skeleton and doctor task ([afe1b6d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/afe1b6d06670f8141446550b3b5cd7ef88d6c7b1))
* **auth:** replace Caddy basic_auth with JupyterLab password auth ([a6c6e3d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a6c6e3ded87016308d1ebea47a3c36857a37e0e4))
* **auth:** replace Caddy basic_auth with JupyterLab password auth ([1922ec0](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1922ec0b60ffe08787cbadb6d1bff72b815b0ca9))
* **caddy:** add /docs, /download, /admin (basic_auth), /api/agent/upload ([dcce76e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/dcce76eb073f88b8c1831c63ab8e2624908e41f4))
* **caddy:** proxy /api/public/* to siteapp ([dcc85fc](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/dcc85fc81bed025f44740474bbb7b0bfc22e5796))
* **caddy:** redirect / to /docs/ so root lands on the public docs portal ([9ac8394](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9ac839456593509751711a7d0c299b6ad79339b1))
* **caddy:** route /grafana/* to grafana:3000 subpath ([eb0b74d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/eb0b74dc3105a09e7c404071e3d9a8e2fe22ac99))
* **chisel:** authorize loki:3100 forward tunnel for every client ([2382be6](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/2382be6f9c169880c64a62ea3278ca2522617039))
* **compose:** add loki and grafana services to render pipeline ([36efb34](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/36efb3424a1aeea89ce82bcc1b2aaa32ed0ffa26))
* **compose:** mount siteapp clients.json and set SITEAPP_CLIENTS_FILE ([039787c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/039787c94dd6d74ef79789b30ceef2ad6b520114))
* **compose:** wire siteapp service + agent_upload_token secret ([b697be4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/b697be46b29fd065926b2c84e0893ebb2b31b759))
* **config:** add loki/grafana config sections and validation ([d9b3304](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/d9b33049a59ee5fd6ae45304fa1b0c7d738600fc))
* **config:** siteapp.image + admin_password_hash; render new __VARS__ ([e4cd8e5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e4cd8e5c6a43b0287445df74f293847cd0456984))
* **deploy:** add deploy.sh with render + rsync + compose up ([4dd1cbe](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/4dd1cbe514b27f56b873334d94e9dc8867e823fb))
* **deploy:** include /api/public/health in post-deploy health check ([56c3baf](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/56c3baf35d5e244bbd604fdfc9ee750dca22482a))
* **deploy:** preflight agent token + healthcheck /docs, /download, /admin (401) ([9bb532a](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9bb532ad98a6ea5577afb459ac4b684c6ce0e7b6))
* **deploy:** render siteapp/clients.json into the staging dir ([1a16907](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1a16907dc6c2f1aa66837a046221f5db1c75d1a5))
* **deploy:** stage loki config, grafana provisioning, admin password ([c6b1a69](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c6b1a6955ddf9360a137684c61630f69868db9f7))
* **docker:** set JupyterLab root directory in docker-compose template ([44bf207](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/44bf2079ef4f8f65cb6823ceb241557aa1d1ac8d))
* **grafana:** provision Loki datasource and Lab client logs dashboard ([6f59850](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6f59850e234830dcda63d9a505f7717366697c83))
* **lib:** add common.sh logging, errors, and SSH wrapper ([a0572ba](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a0572ba7f60550c0e06c4f7d00f2f6e3bc4120d1))
* **lib:** add config.sh with validation and load ([8fe2b37](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/8fe2b37827077d0208c7168d3392e3949c125a00))
* **lib:** add crypto.sh with gen_password and bcrypt_hash ([73b7de0](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/73b7de099ec95ce2abdaf03bcbea4e7533bf3382))
* **loki:** add filesystem-backed config template with retention substitution ([863c13d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/863c13d5a716950340f36057eb25527ac7841887))
* **ops:** add logs:loki, logs:grafana, loki-disk commands ([ac73cdf](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/ac73cdf56b8101d40328b1c8a0093109c5136cac))
* **ops:** add ps/logs/ssh/restart/down/destroy/backup tasks ([416bc94](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/416bc94faebf25956af33fcd93c25da56f8ed6c0))
* **ops:** logs:siteapp and site-disk task entries ([6f0e3c7](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6f0e3c7c56cf15d5a513d473bf257654bdbf89b2))
* **provision:** add provision.sh with Docker, ufw, and dirs ([bf2aaed](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/bf2aaed862d131ecf8d80fd0f6af4e7d3cd55e0d))
* **provision:** create loki_data and grafana_data with correct uids ([23252d5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/23252d5241f4f2c89b3dd5c50df2b8f44501d00c))
* **render:** emit siteapp clients.json from chisel_clients ([a3733d4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a3733d4a3267f46e8c660651641aac58c106d878))
* **render:** render Caddyfile with basic_auth from caddy_users ([6e000e8](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6e000e8e98fe70fd860dd94034d4f358c7a65c6c))
* **render:** render chisel users.json with route restrictions ([628c1dd](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/628c1dd458725d29073d75173bf4c4f6f4082c67))
* **render:** render docker-compose.yml from template ([3145292](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/3145292fde6cfb9b92f5e160a3359dfe38943906))
* **render:** siteapp clients.json emits {port, password_sha256} ([bf713a5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/bf713a533a5085be58524f11607fdcee5de773fc))
* **secrets:** add secrets:add-client task ([7613479](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/7613479119e7ce64441c4d29e5819cd63695551d))
* **secrets:** add secrets:add-user task ([351c819](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/351c8199aa1d445e7f6a7b2b7e8fb84c5dce5ced))
* **secrets:** add set-grafana-password task ([84dfd8d](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/84dfd8d25e9fa6ed5b0fc4e416ed6c36a1c27e8e))
* **secrets:** add set-user-password and rm-user tasks ([340eecd](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/340eecd63363b91d199158add6132179ae8478f9))
* **secrets:** add show-client and rm-client tasks ([66783cb](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/66783cb4a73b9e997a7cb50fcf679c716b55f686))
* **secrets:** task secrets:rotate-agent-upload-token ([12e1fa4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/12e1fa489403179e69c3b08f8e044c52a2b17168))
* **secrets:** task secrets:set-admin-password (caddy hash-password) ([c6b2a52](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c6b2a52cf7b98843a7a1282e1aa859b92285e386))
* **siteapp:** /api/public/clients/{username} with bearer auth ([5228c2e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/5228c2ee6f254cbf8365ec07988ed6e30896e366))
* **siteapp:** /api/public/health proxies chisel server health ([b5b9bab](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/b5b9bab1595a662c47f858066aef428463beab35))
* **siteapp:** /api/public/server-info for agent bootstrap ([#3](https://github.com/bioexperiment-lab-devices/lab-bridge/issues/3)) ([c0074e4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c0074e4432e3dc783a4ddbef7ee93b41cb80c695))
* **siteapp:** /download/agent page and binary stream ([64d0c3e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/64d0c3e4bd7b0c82ac91e6643cc948f529630cde))
* **siteapp:** add generic 4-pane window icon (CC0) ([b849147](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/b849147870b9b6d8882f583801eb85d4771268f9))
* **siteapp:** add load_roster for chisel client discovery ([5701054](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/57010540141518590ab8ee24ff2741a7e71eebd9))
* **siteapp:** add mermaid-init.js (lazy mermaid loader) ([6ad7be9](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6ad7be93c5907d76458cef06909d11b35dbe7465))
* **siteapp:** add SITEAPP_CLIENTS_FILE to Settings ([6f338d0](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6f338d08137a727b167ddcd7860e79872d61a6ca))
* **siteapp:** admin agent page (manual upload + rotate-token UI) ([09c9450](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/09c945015600948b3b8d65034c988179159abb10))
* **siteapp:** admin docs file manager (upload/delete/rename/new-folder) ([79db8e6](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/79db8e6b1c68bb27579a7c4c7f383b2538836ae2))
* **siteapp:** allow-list inline HTML via bleach (img, kbd, ...) ([a21af88](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/a21af88287a4fa122bff08edc9c862e57086763a))
* **siteapp:** build_nav walks docs/ for sidebar tree ([263d213](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/263d2133e568f78e7dae5bc36fcda0e14433c476))
* **siteapp:** build-and-push helper for GHCR ([474b613](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/474b61313ee6c44458649c6ebcc4b994c3d68e3c))
* **siteapp:** Dockerfile (python:3.13-slim + uv frozen sync) ([d4c0490](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/d4c04909b7a40d5bb233cfa706fc4946e997f038))
* **siteapp:** FastAPI skeleton with /healthz and base template ([1eef621](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1eef621fdc67bd9838464b7b4b4889f5250a62e6))
* **siteapp:** GET /api/clients/ — discover chisel tunnel by username ([02c3830](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/02c3830f376a055420182350de0e09cc48af1919))
* **siteapp:** GET /api/clients/ returns chisel client roster ([aa54036](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/aa540362c14f0cb4d64d1e749e6b080a8bf9416c))
* **siteapp:** GitHub-style alert blockquotes ([!NOTE]/[!TIP]/...) ([e2e3e88](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e2e3e884294ab8336ab175e44b44d6dd0d370f07))
* **siteapp:** load mermaid bundle only on pages with diagrams ([0d284b6](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0d284b6aa5ffee1be03cc858f95af912bad636ed))
* **siteapp:** markdown renderer with pygments + anchors ([5876ab1](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/5876ab16b0538f9751e5ef0355dc090451ca7f49))
* **siteapp:** POST /api/agent/upload (bearer token, atomic write) ([44a8981](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/44a898155c585dfa59cfa15f340c08123fda41ec))
* **siteapp:** project scaffolding (uv + pytest + ruff) ([8d1e1c1](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/8d1e1c1f3c1d2a8c9bc4fbb2ef10a98c3d3be41b))
* **siteapp:** public /docs routes with EN/RU + trailing slash ([e83121e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e83121ee4736d0d21267f392e420b5c999f2aac3))
* **siteapp:** public client status & discovery routes ([3339a0c](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/3339a0c743b373efdb54ee5498649b91eb7be54f))
* **siteapp:** public_clients helpers — roster load, bearer parse, verify ([0b82367](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0b8236763a1e231402444ab9756f31e8c7321704))
* **siteapp:** rebrand /download/agent as SerialHop ([0a19340](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/0a19340414ce1a41f7d5eec9b924080c08494a32))
* **siteapp:** render mermaid blocks as &lt;pre class=mermaid&gt; + needs_mermaid flag ([ec1a818](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/ec1a818b56e619e04ce9eb2383534d31e3aebcdd))
* **siteapp:** rewrite default index.md as platform welcome page ([e6099b4](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e6099b4bca7e57ad6dd716dd3f482cfbf420cff3))
* **siteapp:** sanitize_filename + safe_join helpers ([025ffbf](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/025ffbfaff6edc01ec3c5f579bafbd7b7b40ec0f))
* **siteapp:** seed default_docs/ recursively + richer landing page ([96d7dc2](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/96d7dc2a1f92079dbab4359a2ec1f827ddd2f7cc))
* **siteapp:** serve doc-relative images (svg/png/...) from /docs/ ([1e25e85](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/1e25e85a6c1a79cc810b119bfd873ba17238cf51))
* **siteapp:** settings loader (SITE_DATA + token from env or *__FILE) ([44c1529](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/44c152964b2be5b7a416b0dc66ef772f974ff215))
* **siteapp:** TCP probe helper for chisel reverse port liveness ([c268808](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c2688083095312bea09be5dab40833bc3d9f76f5))
* **siteapp:** translation pairing (en/ru with fallback) ([017bf01](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/017bf01b8ea72b9b1dba0a2dbfae93148468b526))
* **siteapp:** vendor jupyter/grafana/github SVG icons ([8090264](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/809026404665c8d5e918c74149d64ca0a7de333e))
* **siteapp:** vendor mermaid.min.js (pinned 11.4.1) ([ac0450e](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/ac0450eb22c2e9ae9d62e6820ce65ebbee692ea2))
* **siteapp:** warn about SmartScreen on agent download page ([d7dc9e0](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/d7dc9e00ed5359b1ce4cd5d8fc370695b2db995e))


### Bug Fixes

* align fake-VPS UIDs with production for jovyan bind-mount ([7f7f189](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/7f7f189fe6728f385138897fa91d62c5a51e12b5))
* **caddy:** add default_sni so IP-only TLS works for SNI-less clients ([c49f0a3](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/c49f0a3ca91a57cfeeaebc5ccd4569e94e38a977))
* **caddy:** drop issuer internal — ACME-only, fail loud on issuance error ([f6567c7](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/f6567c7f3f4f98c7b298f7ef63cddf1ff5bdf7ad))
* **caddy:** preserve /grafana prefix on upstream so Grafana sub-path stops looping ([647afac](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/647afac9f6c4562edb6ba926dff3da3d05e7116a))
* **caddy:** route /_static/* to siteapp so templates load CSS/JS ([e7a7893](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/e7a7893baf2c16a75528acfb0f7339f92045f0c4))
* **deploy:** also exclude caddy_config from rsync --delete ([fe8235f](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/fe8235f023cc64b57cfb25b56468f91c5bb4b7a3))
* **deploy:** ensure caddy and chisel restart on config changes ([9ae4dae](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9ae4dae90efd5a9a4096677dbf7999e577e3b498))
* **deploy:** probe /grafana/ in healthcheck so a crash-looping grafana/loki fails the deploy ([56ccde9](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/56ccde9c2d33e164884d3ca9f71fa765cf7b7ed7))
* **deploy:** restart caddy + drop tls-shorthand to match issuer block ([f770945](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/f7709456db128c98da1a75df66e9b806bdb3e303))
* **deploy:** stage grafana admin_password as 0644 so the container can read it ([9c04b99](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9c04b99cf9df7ae2d0958d06cf6663d91acc8d77))
* **grafana:** replace invalid max_over_time on log stream with count_over_time ([6529f47](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6529f479c88ab19163d3c7e8063b449a2a7fddb2))
* **render:** stop silencing yq errors in render_siteapp_clients ([9855b06](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9855b067de344119195a23e18f61f794e6c95a54))
* **secrets:** drop removed --plaintext-stdin flag from caddy hash-password ([679438f](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/679438f647d819b89d03774ef43a6b2566518013))
* **siteapp:** admin rename must keep an allowed file extension ([51f9568](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/51f95688422c7d306871e4eb9b3a83c0c777299c))
* **siteapp:** admin target sanitization, new-folder 4xx, jinja breadcrumb namespace ([47d6b64](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/47d6b64b14e188770aef397c48e44eafe502b4c8))
* **siteapp:** broaden upload_agent .part cleanup to all exceptions ([6ae53d2](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/6ae53d2e4b87034c00c171d2a2d9f50542e40d56))
* **siteapp:** close /docs/..%2F traversal leak; tighten cookie flags ([9d5dfc6](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/9d5dfc63ac5c6e259ab4c3a548d5a0c7e78c6982))
* **siteapp:** extract title from token tree; skip guess_lexer; +regression tests ([bc4afd5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/bc4afd5e4de26948b8dac32b09d9141a991f3dd1))
* **siteapp:** load mermaid as classic deferred scripts (UMD bundle, not ES module) ([071fed5](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/071fed5741de1ce38c6fdb3e70610074b5b9c5e3))
* **siteapp:** preserve table alignment + footnote markup through bleach ([d378924](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/d378924a81247dbeb58c176670820d5515fcbac8))
* **siteapp:** seed default docs/index.md so fresh deploys pass healthcheck ([ffc2410](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/ffc241028cc2a43817a3233a01dabf22ce5f5d1c))
* **siteapp:** single &lt;pre&gt; per fenced code block ([5545c5f](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/5545c5f1152080627034a2f43f208f04d5c02132))
* **siteapp:** validate roster entry shape in _load_roster ([8944c30](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/8944c3000682618b49e3a97ab95d3886f94a5ecd))
* update valid_config fixture hash to 53 chars ([8db76cb](https://github.com/bioexperiment-lab-devices/lab-bridge/commit/8db76cb187f51b3969d9b82a056811f30f69de8e))
