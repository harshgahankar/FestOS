/* Aarohan poster artwork (user-provided SVG strings), rendered via innerHTML.
   SVGs use class attributes instead of JSX, so keep them as raw strings. */

export const scene = `
<svg class="scene" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
 <defs>
  <linearGradient id="wallY" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#eec25a"/><stop offset=".72" stop-color="#dca43a"/><stop offset="1" stop-color="#c98f2e"/></linearGradient>
  <linearGradient id="wallC" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#f2e2b0"/><stop offset=".8" stop-color="#e3c88d"/><stop offset="1" stop-color="#d4b177"/></linearGradient>
  <radialGradient id="floorGlow" cx=".5" cy="1" r=".8"><stop offset="0" stop-color="#e06a2f" stop-opacity=".4"/><stop offset=".6" stop-color="#e06a2f" stop-opacity=".1"/><stop offset="1" stop-color="#e06a2f" stop-opacity="0"/></radialGradient>
  <filter id="soft"><feGaussianBlur stdDeviation="16"/></filter>
  <path id="pet" d="M0 -236 C 20 -196 20 -148 0 -110 C -20 -148 -20 -196 0 -236 Z" fill="none" stroke="#e08a52" stroke-width="3"/>
  <path id="dropP" d="M0 0 C 12 22 20 30 14 44 C 8 56 -8 56 -14 44 C -20 30 -12 22 0 0 Z"/>
 </defs>
 <rect width="1600" height="900" fill="#a53028"/>
 <g opacity=".55" transform="translate(1466,420)">
  <circle r="252" fill="none" stroke="#e08a52" stroke-width="2.5"/>
  <circle r="208" fill="none" stroke="#e08a52" stroke-width="7" stroke-dasharray="2 22"/>
  <circle r="162" fill="none" stroke="#e08a52" stroke-width="3"/>
  <circle r="96" fill="none" stroke="#e08a52" stroke-width="9" stroke-dasharray="42 24"/>
  <circle r="58" fill="none" stroke="#e08a52" stroke-width="3.5"/>
  <circle r="9" fill="#e08a52"/>
  <use href="#pet" transform="rotate(0)"/><use href="#pet" transform="rotate(30)"/><use href="#pet" transform="rotate(60)"/><use href="#pet" transform="rotate(90)"/><use href="#pet" transform="rotate(120)"/><use href="#pet" transform="rotate(150)"/><use href="#pet" transform="rotate(180)"/><use href="#pet" transform="rotate(210)"/><use href="#pet" transform="rotate(240)"/><use href="#pet" transform="rotate(270)"/><use href="#pet" transform="rotate(300)"/><use href="#pet" transform="rotate(330)"/>
 </g>
 <g opacity=".34" transform="translate(46,260) scale(1.55) rotate(14)">
  <circle r="252" fill="none" stroke="#e08a52" stroke-width="2.5"/>
  <circle r="180" fill="none" stroke="#e08a52" stroke-width="6" stroke-dasharray="2 22"/>
  <circle r="96" fill="none" stroke="#e08a52" stroke-width="9" stroke-dasharray="42 24"/>
  <use href="#pet" transform="rotate(0)"/><use href="#pet" transform="rotate(60)"/><use href="#pet" transform="rotate(120)"/><use href="#pet" transform="rotate(180)"/><use href="#pet" transform="rotate(240)"/><use href="#pet" transform="rotate(300)"/>
 </g>
 <g stroke="#d66a3f" stroke-width="3" fill="none" opacity=".4">
  <path d="M420 214 q95 -72 215 -50"/>
  <path d="M480 128 q72 -32 154 -20"/>
  <path d="M1055 152 q82 -42 172 -22"/>
  <path d="M1160 254 q112 -62 226 -32"/>
  <path d="M540 330 a44 44 0 1 1 66 34"/>
 </g>
 <g filter="url(#soft)">
  <ellipse cx="300" cy="66" rx="210" ry="54" fill="#d8d3a0" opacity=".13"/>
  <ellipse cx="1330" cy="52" rx="190" ry="48" fill="#d8d3a0" opacity=".12"/>
  <ellipse cx="70" cy="540" rx="120" ry="160" fill="#e3c27a" opacity=".1"/>
  <ellipse cx="1540" cy="560" rx="110" ry="150" fill="#e3c27a" opacity=".1"/>
 </g>
 <path d="M0 648 H1600 V900 H0 Z" fill="#b33a26"/>
 <path d="M0 648 H1600" stroke="#7f1f15" stroke-width="5" opacity=".6"/>
 <path d="M0 700 H1600 V900 H0 Z" fill="url(#floorGlow)"/>
 <g stroke="#8a231b" stroke-width="3" opacity=".75" stroke-linecap="round" fill="none">
  <path d="M0 678 H430 M480 678 H930 M985 678 H1600"/>
  <path d="M0 724 H300 M365 724 H835 M905 724 H1275 M1330 724 H1600"/>
  <path d="M0 772 H225 M290 772 H715 M775 772 H1195 M1255 772 H1600"/>
  <path d="M0 830 H185 M245 830 H655 M715 830 H1135 M1195 830 H1600"/>
  <path d="M0 878 H625 M685 878 H1600"/>
  <path d="M205 678 V724 M545 678 V724 M965 678 V724 M1410 678 V724"/>
  <path d="M110 724 V772 M440 724 V772 M788 724 V772 M1160 724 V772 M1495 724 V772"/>
  <path d="M305 772 V830 M655 772 V830 M1015 772 V830 M1365 772 V830"/>
  <path d="M95 830 V878 M490 830 V878 M875 830 V878 M1310 830 V878"/>
 </g>
 <g fill="#7c1e15" opacity=".45">
  <rect x="600" y="850" width="26" height="7" rx="3"/><rect x="950" y="806" width="32" height="8" rx="4"/><rect x="1210" y="866" width="24" height="6" rx="3"/><rect x="330" y="862" width="30" height="7" rx="3"/>
 </g>
 <g class="left-town">
  <rect x="-12" y="100" width="266" height="600" fill="url(#wallY)"/>
  <rect x="216" y="100" width="38" height="600" fill="#b9872f" opacity=".5"/>
  <g fill="#c2842f"><rect x="-10" y="88" width="16" height="14"/><rect x="24" y="88" width="16" height="14"/><rect x="58" y="88" width="16" height="14"/><rect x="92" y="88" width="16" height="14"/><rect x="126" y="88" width="16" height="14"/><rect x="160" y="88" width="16" height="14"/><rect x="194" y="88" width="16" height="14"/><rect x="228" y="88" width="16" height="14"/></g>
  <rect x="-12" y="100" width="266" height="8" fill="#a8702f"/>
  <path d="M76 96 q29 -48 58 0 Z" fill="#efc25a"/>
  <rect x="103" y="38" width="5" height="18" fill="#8a5a1e"/><circle cx="105" cy="36" r="5" fill="#e8c24f"/>
  <g fill="#2f9d97" stroke="#43221a" stroke-width="5">
   <path d="M44 232 a23 23 0 0 1 46 0 v50 h-46 Z"/><path d="M132 232 a23 23 0 0 1 46 0 v50 h-46 Z"/>
  </g>
  <g stroke="#43221a" stroke-width="2.5"><path d="M67 208 V282 M155 208 V282"/></g>
  <g fill="#6f3d1c" stroke="#43221a" stroke-width="4">
   <rect x="40" y="424" width="46" height="76"/><rect x="112" y="424" width="46" height="76"/><rect x="184" y="424" width="46" height="76"/>
  </g>
  <g stroke="#43221a" stroke-width="4"><path d="M63 424 V500 M135 424 V500 M207 424 V500 M40 462 H86 M112 462 H158 M184 462 H230"/></g>
  <g fill="#b5713a"><rect x="34" y="500" width="58" height="8"/><rect x="106" y="500" width="58" height="8"/><rect x="178" y="500" width="58" height="8"/></g>
  <g stroke="#d8a844" stroke-width="3" opacity=".5"><path d="M20 200 V660 M96 190 V660 M172 200 V660"/></g>
  <rect x="238" y="398" width="216" height="342" fill="url(#wallC)"/>
  <rect x="238" y="398" width="216" height="10" fill="#a87838"/>
  <rect x="418" y="398" width="36" height="342" fill="#d0ac66" opacity=".55"/>
  <rect x="252" y="432" width="92" height="26" fill="#f3cf5f" stroke="#43221a" stroke-width="4"/>
  <g fill="#79261e" stroke="#43221a" stroke-width="4"><rect x="262" y="478" width="34" height="44"/><rect x="322" y="478" width="34" height="44"/><rect x="382" y="478" width="34" height="44"/></g>
  <path d="M306 740 v-104 a36 36 0 0 1 72 0 v104 Z" fill="#2f9d97" stroke="#43221a" stroke-width="5"/>
  <path d="M342 640 V740" stroke="#43221a" stroke-width="3"/>
  <ellipse cx="430" cy="420" rx="40" ry="26" fill="#b7b98a" opacity=".28" filter="url(#soft)"/>
 </g>
 <g class="lamp">
  <rect x="318" y="258" width="11" height="470" fill="#33281d"/>
  <rect x="310" y="722" width="28" height="16" fill="#33281d"/>
  <path d="M323 268 q-8 -42 -50 -42" fill="none" stroke="#33281d" stroke-width="9"/>
  <path d="M258 224 h30 v6 l7 9 v22 l-7 9 h-30 l-7 -9 v-22 l7 -9 Z" fill="#3a2c1e"/>
  <rect x="263" y="239" width="21" height="19" fill="#ffdf6e"/>
  <path d="M254 224 h38 l-19 -15 Z" fill="#33281d"/>
  <circle cx="273" cy="248" r="27" fill="#ffdf6e" opacity=".3" filter="url(#soft)"/>
 </g>
 <g class="banana">
  <path d="M372 648 C 382 542 432 472 508 452 C 472 522 442 584 416 650 Z" fill="#4c8a3e"/>
  <path d="M376 644 C 402 574 452 502 506 456" fill="none" stroke="#38682e" stroke-width="4"/>
  <path d="M342 652 C 320 562 280 506 226 490 C 272 546 312 604 348 654 Z" fill="#3c7a33"/>
  <path d="M344 648 C 316 588 284 532 228 494" fill="none" stroke="#2f5f28" stroke-width="4"/>
  <path d="M362 654 C 364 592 382 546 418 524 C 408 572 390 610 372 656 Z" fill="#5fa049"/>
 </g>
 <ellipse cx="180" cy="798" rx="165" ry="13" fill="#7c1e15" opacity=".4"/>
 <g class="cart">
  <g fill="#6f3d1c"><rect x="62" y="446" width="9" height="256"/><rect x="292" y="446" width="9" height="256"/></g>
  <path d="M34 446 L318 444 L318 478 L34 480 Z" fill="#e2993a" stroke="#43221a" stroke-width="4"/>
  <g stroke="#43221a" stroke-width="3">
   <path d="M34 480 a18 16 0 0 0 36 0 Z" fill="#2f9d97"/><path d="M70 480 a18 16 0 0 0 36 0 Z" fill="#f2e2b0"/><path d="M106 480 a18 16 0 0 0 36 0 Z" fill="#2f9d97"/><path d="M142 480 a18 16 0 0 0 36 0 Z" fill="#f2e2b0"/><path d="M178 480 a18 16 0 0 0 36 0 Z" fill="#2f9d97"/><path d="M214 480 a18 16 0 0 0 36 0 Z" fill="#f2e2b0"/><path d="M250 480 a18 16 0 0 0 36 0 Z" fill="#2f9d97"/><path d="M286 480 a18 16 0 0 0 32 0 Z" fill="#f2e2b0"/>
  </g>
  <rect x="44" y="556" width="272" height="32" fill="#f0d68f" stroke="#43221a" stroke-width="4"/>
  <g>
   <g fill="#f7ecd4" stroke="#43221a" stroke-width="3"><rect x="66" y="524" width="24" height="34" rx="4"/><rect x="94" y="524" width="24" height="34" rx="4"/><rect x="122" y="524" width="24" height="34" rx="4"/><rect x="150" y="524" width="24" height="34" rx="4"/><rect x="178" y="524" width="24" height="34" rx="4"/><rect x="206" y="524" width="24" height="34" rx="4"/><rect x="234" y="524" width="24" height="34" rx="4"/><rect x="262" y="524" width="24" height="34" rx="4"/></g>
   <g fill="#e8c24f" opacity=".55"><rect x="70" y="520" width="16" height="8"/><rect x="98" y="520" width="16" height="8"/><rect x="126" y="520" width="16" height="8"/><rect x="154" y="520" width="16" height="8"/><rect x="182" y="520" width="16" height="8"/><rect x="210" y="520" width="16" height="8"/><rect x="238" y="520" width="16" height="8"/><rect x="266" y="520" width="16" height="8"/></g>
  </g>
  <rect x="52" y="588" width="256" height="116" fill="url(#wallY)" stroke="#43221a" stroke-width="5"/>
  <g stroke="#43221a" stroke-width="3"><path d="M52 622 H308 M52 656 H308 M52 690 H308"/></g>
  <g>
   <circle cx="130" cy="750" r="56" fill="#6f3d1c" stroke="#43221a" stroke-width="9"/>
   <circle cx="130" cy="750" r="42" fill="none" stroke="#efc25a" stroke-width="5"/>
   <g stroke="#efc25a" stroke-width="4"><path d="M86 750 H174 M130 706 V794 M100 720 L160 780 M100 780 L160 720"/></g>
   <circle cx="130" cy="750" r="9" fill="#f6e8cf" stroke="#43221a" stroke-width="3"/>
   <circle cx="284" cy="764" r="26" fill="#6f3d1c" stroke="#43221a" stroke-width="7"/>
   <circle cx="284" cy="764" r="6" fill="#f6e8cf"/>
  </g>
 </g>
 <g class="right-town">
  <path d="M1456 250 q27 -44 54 0 Z" fill="#efc25a"/>
  <rect x="1456" y="240" width="6" height="14" fill="#8a5a1e"/><circle cx="1459" cy="238" r="5" fill="#e8c24f"/>
  <rect x="1450" y="250" width="162" height="530" fill="url(#wallY)"/>
  <rect x="1586" y="250" width="26" height="530" fill="#c98f2e" opacity=".55"/>
  <rect x="1450" y="250" width="162" height="8" fill="#a8702f"/>
  <g fill="#2f9d97" stroke="#43221a" stroke-width="5">
   <path d="M1502 344 a26 26 0 0 1 52 0 v58 h-52 Z"/><path d="M1502 496 a26 26 0 0 1 52 0 v52 h-52 Z"/>
  </g>
  <g stroke="#43221a" stroke-width="2.5"><path d="M1528 320 V402 M1528 472 V548"/></g>
  <path d="M1518 780 v-108 a32 32 0 0 1 64 0 v108 Z" fill="#238f88" stroke="#43221a" stroke-width="5"/>
  <path d="M1550 668 V780" stroke="#43221a" stroke-width="3"/>
  <path d="M1454 272 Q 1364 306 1282 284" fill="none" stroke="#f6e3b4" stroke-width="3"/>
  <g><path d="M1300 286 l22 -4 l-10 26 Z" fill="#d8472f"/><path d="M1342 296 l22 -3 l-11 26 Z" fill="#2fa8a2"/><path d="M1384 300 l22 -2 l-11 25 Z" fill="#f0b23a"/><path d="M1426 294 l22 -3 l-11 25 Z" fill="#d8472f"/></g>
  <rect x="1302" y="470" width="160" height="330" fill="url(#wallC)"/>
  <rect x="1302" y="470" width="160" height="9" fill="#a87838"/>
  <rect x="1302" y="470" width="22" height="330" fill="#d0ac66" opacity=".5"/>
  <g fill="#6f3d1c" stroke="#43221a" stroke-width="4"><rect x="1326" y="516" width="36" height="48"/><rect x="1398" y="516" width="36" height="48"/></g>
  <g fill="#23a3a0" stroke="#43221a" stroke-width="4">
   <path d="M1334 800 v-102 a26 26 0 0 1 52 0 v102 Z"/>
   <path d="M1392 800 v-102 a26 26 0 0 1 42 0 v102 Z" transform="translate(0,0)"/>
  </g>
  <path d="M1347 700 H1418" stroke="#43221a" stroke-width="3"/>
  <g fill="#edd9a4" stroke="#43221a" stroke-width="3"><rect x="1318" y="800" width="150" height="14"/><rect x="1332" y="814" width="122" height="14"/></g>
  <g><ellipse cx="1323" cy="742" rx="22" ry="20" fill="#3f7d36"/><ellipse cx="1341" cy="734" rx="17" ry="15" fill="#5fa049"/><rect x="1309" y="760" width="32" height="24" fill="#b06a2e" stroke="#43221a" stroke-width="3"/></g>
  <path d="M1600 706 C 1556 646 1544 592 1572 546 C 1598 594 1606 652 1600 706 Z" fill="#4c8a3e"/>
  <path d="M1600 692 C 1566 620 1584 570 1616 548 C 1608 614 1604 656 1600 692 Z" fill="#5fa049"/>
  <rect x="1488" y="776" width="112" height="34" fill="#e9d6a2" stroke="#43221a" stroke-width="4"/>
  <rect x="1488" y="770" width="112" height="8" fill="#f4e6bd"/>
  <rect x="1508" y="810" width="92" height="46" fill="#d8c08c" stroke="#43221a" stroke-width="4"/>
 </g>
 <ellipse cx="1172" cy="806" rx="142" ry="14" fill="#7c1e15" opacity=".45"/>
 <svg class="rickshaw" x="1016" y="584" width="312" height="223" viewBox="0 0 140 100" aria-hidden="true" focusable="false"><path d="M27 20h66l16 38H19z" fill="#f5c400" stroke="#4a211d" stroke-width="4"/><path d="M34 27h24v26H27zm31 0h22l10 26H65z" fill="#24b9b3" stroke="#4a211d" stroke-width="3"/><path d="M19 57h90l18 20v9H15V64z" fill="#24b9b3" stroke="#4a211d" stroke-width="4"/><circle cx="35" cy="84" r="12" fill="#4a211d"/><circle cx="108" cy="84" r="12" fill="#4a211d"/><circle cx="35" cy="84" r="5" fill="#f6e8cf"/><circle cx="108" cy="84" r="5" fill="#f6e8cf"/><path d="M10 18h90" stroke="#4a211d" stroke-width="8"/><path d="M112 65h10" stroke="#f5c400" stroke-width="7"/></svg>
 <g class="bunting">
  <path d="M-10 62 Q 215 184 436 100" fill="none" stroke="#f6e3b4" stroke-width="3"/>
  <g>
   <path d="M28 96 l24 -4 l-12 38 Z" fill="#2fa8a2"/>
   <path d="M84 128 l24 -3 l-12 38 Z" fill="#d8472f"/>
   <path d="M142 150 l24 -3 l-12 38 Z" fill="#f0b23a"/>
   <path d="M200 158 l24 -3 l-12 38 Z" fill="#e8963c"/>
   <path d="M258 152 l24 -3 l-12 38 Z" fill="#2fa8a2"/>
   <path d="M316 138 l24 -3 l-12 36 Z" fill="#d8472f"/>
   <path d="M372 120 l24 -3 l-12 36 Z" fill="#f0b23a"/>
   <path d="M420 106 l24 -3 l-12 36 Z" fill="#2fa8a2"/>
  </g>
  <path d="M-10 148 Q 130 226 268 172" fill="none" stroke="#f6e3b4" stroke-width="2.5"/>
  <g>
   <path d="M14 160 l20 -2 l-10 30 Z" fill="#d8472f"/>
   <path d="M62 192 l20 -2 l-10 30 Z" fill="#f0b23a"/>
   <path d="M114 206 l20 -2 l-10 30 Z" fill="#2fa8a2"/>
   <path d="M168 198 l20 -2 l-10 30 Z" fill="#e8963c"/>
   <path d="M216 182 l20 -2 l-10 30 Z" fill="#d8472f"/>
  </g>
  <path d="M1280 62 H1600" stroke="#c8452e" stroke-width="3"/>
  <g fill="#d8472f"><path d="M1322 64 l22 -1 l-11 26 Z"/><path d="M1372 64 l22 0 l-11 25 Z"/><path d="M1422 64 l22 1 l-11 25 Z"/><path d="M1472 66 l22 3 l-10 25 Z"/><path d="M1526 70 l22 5 l-10 24 Z"/></g>
 </g>
</svg>`;

export const flourishTop = `
<svg class="flourish top" viewBox="0 0 320 96" aria-hidden="true" focusable="false">
 <path d="M160 82 C 138 78 126 58 130 38 C 150 45 158 62 160 82" fill="#1fa39c"/>
 <path d="M160 82 C 182 78 194 58 190 38 C 170 45 162 62 160 82" fill="#1fa39c"/>
 <path d="M160 4 C 170 24 178 32 172 46 C 166 58 154 58 148 46 C 142 32 150 24 160 4 Z" fill="#f0b23a"/>
 <path d="M118 26 C 122 42 130 48 126 58 C 116 52 110 36 118 26 Z" fill="#f0b23a"/>
 <path d="M202 26 C 198 42 190 48 194 58 C 204 52 210 36 202 26 Z" fill="#f0b23a"/>
 <rect x="156" y="84" width="9" height="9" fill="#c9472c" transform="rotate(45 160.5 88.5)"/>
</svg>`;

export const flourishBottom = `
<svg class="flourish bottom" viewBox="0 0 320 96" aria-hidden="true" focusable="false">
 <path d="M160 14 C 138 18 126 38 130 58 C 150 51 158 34 160 14" fill="#1fa39c"/>
 <path d="M160 14 C 182 18 194 38 190 58 C 170 51 162 34 160 14" fill="#1fa39c"/>
 <path d="M160 92 C 170 72 178 64 172 50 C 166 38 154 38 148 50 C 142 64 150 72 160 92 Z" fill="#f0b23a"/>
 <path d="M118 70 C 122 54 130 48 126 38 C 116 44 110 60 118 70 Z" fill="#f0b23a"/>
 <path d="M202 70 C 198 54 190 48 194 38 C 204 44 210 60 202 70 Z" fill="#f0b23a"/>
 <rect x="156" y="3" width="9" height="9" fill="#c9472c" transform="rotate(45 160.5 7.5)"/>
</svg>`;

export const splashLeft = `
<svg class="splash left" viewBox="0 0 110 130" aria-hidden="true" focusable="false">
 <path d="M30 4 C 44 34 54 46 46 66 C 30 56 20 24 30 4 Z" fill="#f0b23a"/>
 <path d="M62 16 C 70 34 76 42 70 56 C 58 48 52 30 62 16 Z" fill="#f0b23a"/>
 <path d="M20 78 C 32 94 38 102 32 114 C 20 106 12 90 20 78 Z" fill="#1fa39c"/>
</svg>`;

export const splashRight = `
<svg class="splash right" viewBox="0 0 150 180" aria-hidden="true" focusable="false">
 <path d="M46 12 C 66 52 82 72 70 102 C 46 88 30 44 46 12 Z" fill="#f0b23a"/>
 <path d="M84 24 C 96 48 104 60 96 80 C 78 68 68 44 84 24 Z" fill="#f0b23a"/>
 <path d="M108 60 C 118 78 122 88 114 104 C 100 94 94 74 108 60 Z" fill="#1fa39c"/>
 <path d="M56 116 C 68 138 76 148 68 164 C 50 152 42 130 56 116 Z" fill="#f0b23a"/>
</svg>`;

export const sprigLeft = `
<svg class="sprig" viewBox="0 0 78 56" aria-hidden="true" focusable="false">
 <path d="M40 28 C 26 24 18 12 22 2 C 34 8 40 18 40 28 Z" fill="#f0b23a"/>
 <path d="M38 28 C 52 24 60 12 56 2 C 44 8 38 18 38 28 Z" fill="#f0b23a"/>
 <path d="M39 28 C 30 40 22 44 14 40 C 22 34 30 30 39 28 Z" fill="#1fa39c"/>
 <path d="M39 28 C 48 40 56 44 64 40 C 56 34 48 30 39 28 Z" fill="#1fa39c"/>
 <rect x="35" y="28" width="8" height="8" fill="#f0b23a" transform="rotate(45 39 32)"/>
</svg>`;

export const sprigRight = `
<svg class="sprig right" viewBox="0 0 78 56" aria-hidden="true" focusable="false">
 <path d="M39 28 C 25 32 17 44 21 54 C 33 48 39 38 39 28 Z" fill="#f0b23a"/>
 <path d="M39 28 C 53 32 61 44 57 54 C 45 48 39 38 39 28 Z" fill="#f0b23a"/>
 <path d="M39 28 C 30 16 22 12 14 16 C 22 22 30 26 39 28 Z" fill="#1fa39c"/>
 <path d="M39 28 C 48 16 56 12 64 16 C 56 22 48 26 39 28 Z" fill="#1fa39c"/>
 <rect x="35" y="20" width="8" height="8" fill="#f0b23a" transform="rotate(45 39 24)"/>
</svg>`;

export const tear = `
<svg class="tear" viewBox="0 0 1600 44" preserveAspectRatio="none" aria-hidden="true" focusable="false">
 <path d="M0 0 H1600 V7 L1556 18 1494 9 1432 21 1366 10 1288 23 1206 10 1124 21 1042 8 952 19 862 8 772 21 682 10 592 21 502 9 412 19 322 9 232 19 142 10 62 21 0 11 Z" fill="#f2e3bd"/>
 <path d="M0 0 H1600 V3 L1520 11 1420 4 1320 13 1220 4 1120 13 1010 4 910 13 800 4 700 13 600 4 500 13 400 4 300 11 200 4 100 11 0 4 Z" fill="#fbf3dd"/>
</svg>`;
