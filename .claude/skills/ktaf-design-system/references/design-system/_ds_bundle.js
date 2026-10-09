/* @ds-bundle: {"format":4,"namespace":"KIPPNJMiamiDesignSystem_1916b9","components":[{"name":"Button","sourcePath":"components/actions/Button.jsx"},{"name":"IconButton","sourcePath":"components/actions/IconButton.jsx"},{"name":"Avatar","sourcePath":"components/display/Avatar.jsx"},{"name":"AvatarGroup","sourcePath":"components/display/Avatar.jsx"},{"name":"Badge","sourcePath":"components/display/Badge.jsx"},{"name":"Card","sourcePath":"components/display/Card.jsx"},{"name":"StatCallout","sourcePath":"components/display/StatCallout.jsx"},{"name":"Tag","sourcePath":"components/display/Tag.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Switch","sourcePath":"components/forms/Switch.jsx"},{"name":"SegmentedControl","sourcePath":"components/navigation/SegmentedControl.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"}],"sourceHashes":{"components/actions/Button.jsx":"49745a552ae7","components/actions/IconButton.jsx":"0eb6ba779ce3","components/display/Avatar.jsx":"2ae7abd674b9","components/display/Badge.jsx":"0c2c4df9daad","components/display/Card.jsx":"c7fedba16330","components/display/StatCallout.jsx":"557178ea6b27","components/display/Tag.jsx":"a547635a985e","components/forms/Checkbox.jsx":"dcee1272d921","components/forms/Input.jsx":"7098d10ea049","components/forms/Select.jsx":"bb43565855f9","components/forms/Switch.jsx":"c4daed59801a","components/internal/useDSStyle.js":"9d32fd2306df","components/navigation/SegmentedControl.jsx":"2acbf2548f0b","components/navigation/Tabs.jsx":"880f31db9387","ui_kits/data-dashboard/Charts.jsx":"50afeebcc445","ui_kits/data-dashboard/DashBody.jsx":"164ef0e79f76","ui_kits/data-dashboard/DashSidebar.jsx":"749fbff7dc33","ui_kits/data-dashboard/DashTopbar.jsx":"5a1efc2ecd53","ui_kits/data-dashboard/DataTable.jsx":"c32bef050b0a","ui_kits/website/ApplyModal.jsx":"cab1332d3c2c","ui_kits/website/CTABand.jsx":"40bdf525987f","ui_kits/website/Hero.jsx":"a179408edfb1","ui_kits/website/PhotoFrame.jsx":"0036f35afc69","ui_kits/website/SchoolFinder.jsx":"cacf2c41e0b1","ui_kits/website/SiteFooter.jsx":"f1530db0890a","ui_kits/website/SiteHeader.jsx":"5168e0f2e531","ui_kits/website/StatBand.jsx":"649dce6c0bd4","ui_kits/website/ValueProps.jsx":"d51d46c9d196"},"inlinedExternals":[],"unexposedExports":[{"name":"useDSStyle","sourcePath":"components/internal/useDSStyle.js"}]} */

(() => {

const __ds_ns = (window.KIPPNJMiamiDesignSystem_1916b9 = window.KIPPNJMiamiDesignSystem_1916b9 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/internal/useDSStyle.js
try { (() => {
/**
 * Shared one-time <style> injector for design-system components.
 * Keeps components self-contained while still giving real
 * :hover / :focus / :active states driven by brand tokens.
 */
const injected = new Set();
function useDSStyle(id, css) {
  if (typeof document === 'undefined') return;
  if (injected.has(id)) return;
  injected.add(id);
  const el = document.createElement('style');
  el.setAttribute('data-ds', id);
  el.textContent = css;
  document.head.appendChild(el);
}
Object.assign(__ds_scope, { useDSStyle });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/internal/useDSStyle.js", error: String((e && e.message) || e) }); }

// components/actions/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-btn{
  --_bg:var(--kipp-indigo); --_fg:var(--kipp-white); --_bd:transparent;
  display:inline-flex; align-items:center; justify-content:center; gap:8px;
  font-family:var(--font-brand); font-weight:600; text-transform:uppercase;
  letter-spacing:.04em; line-height:1; white-space:nowrap; cursor:pointer;
  border:var(--border-width-strong) solid var(--_bd); border-radius:var(--radius-md);
  background:var(--_bg); color:var(--_fg);
  transition:transform var(--dur-fast) var(--ease-standard),
             background var(--dur-fast) var(--ease-standard),
             box-shadow var(--dur-fast) var(--ease-standard), filter var(--dur-fast) var(--ease-standard);
}
.kf-btn:hover{ filter:brightness(1.06); transform:translateY(var(--hover-lift)); }
.kf-btn:active{ transform:scale(var(--press-scale)); filter:brightness(.96); }
.kf-btn:focus-visible{ outline:none; box-shadow:var(--ring); }
.kf-btn[disabled]{ opacity:.45; cursor:not-allowed; transform:none; filter:none; }

/* sizes */
.kf-btn--sm{ font-size:12px; padding:8px 14px; }
.kf-btn--md{ font-size:13px; padding:11px 20px; }
.kf-btn--lg{ font-size:15px; padding:15px 28px; }

/* variants */
.kf-btn--primary{ --_bg:var(--kipp-indigo); --_fg:var(--kipp-white); }
.kf-btn--accent{ --_bg:var(--brand-accent); --_fg:var(--brand-on-accent); }
.kf-btn--secondary{ --_bg:transparent; --_fg:var(--kipp-indigo); --_bd:var(--kipp-indigo); }
.kf-btn--secondary:hover{ background:var(--indigo-50); filter:none; }
.kf-btn--ghost{ --_bg:transparent; --_fg:var(--kipp-indigo); --_bd:transparent; }
.kf-btn--ghost:hover{ background:var(--indigo-50); filter:none; }
.kf-btn--block{ width:100%; }
`;

/**
 * Button — the primary brand action. Bold, all-caps, confident.
 */
function Button({
  children,
  variant = 'primary',
  size = 'md',
  block = false,
  iconLeft = null,
  iconRight = null,
  type = 'button',
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-btn', CSS);
  const cls = ['kf-btn', `kf-btn--${variant}`, `kf-btn--${size}`, block ? 'kf-btn--block' : '', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    className: cls
  }, rest), iconLeft, children, iconRight);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/actions/Button.jsx", error: String((e && e.message) || e) }); }

// components/actions/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-iconbtn{
  --_bg:transparent; --_fg:var(--kipp-indigo); --_bd:transparent;
  display:inline-flex; align-items:center; justify-content:center;
  border:var(--border-width-strong) solid var(--_bd); border-radius:var(--radius-md);
  background:var(--_bg); color:var(--_fg); cursor:pointer; padding:0;
  transition:background var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}
.kf-iconbtn svg{ width:60%; height:60%; }
.kf-iconbtn:hover{ background:var(--indigo-50); }
.kf-iconbtn:active{ transform:scale(var(--press-scale)); }
.kf-iconbtn:focus-visible{ outline:none; box-shadow:var(--ring); }
.kf-iconbtn[disabled]{ opacity:.45; cursor:not-allowed; }
.kf-iconbtn--sm{ width:32px; height:32px; }
.kf-iconbtn--md{ width:40px; height:40px; }
.kf-iconbtn--lg{ width:48px; height:48px; }
.kf-iconbtn--solid{ --_bg:var(--kipp-indigo); --_fg:var(--kipp-white); }
.kf-iconbtn--solid:hover{ background:var(--indigo-700); }
.kf-iconbtn--accent{ --_bg:var(--brand-accent); --_fg:var(--brand-on-accent); }
.kf-iconbtn--outline{ --_bd:var(--border-default); }
.kf-iconbtn--pill{ border-radius:var(--radius-pill); }
`;

/**
 * IconButton — square (or pill) tappable control wrapping a single icon.
 */
function IconButton({
  children,
  variant = 'ghost',
  size = 'md',
  pill = false,
  label,
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-iconbtn', CSS);
  const cls = ['kf-iconbtn', `kf-iconbtn--${variant}`, `kf-iconbtn--${size}`, pill ? 'kf-iconbtn--pill' : '', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    "aria-label": label,
    title: label,
    className: cls
  }, rest), children);
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/actions/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/display/Avatar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-avatar{
  display:inline-flex; align-items:center; justify-content:center;
  border-radius:var(--radius-pill); overflow:hidden; flex:none;
  font-family:var(--font-brand); font-weight:700; text-transform:uppercase;
  background:var(--indigo-100); color:var(--indigo-700);
  border:2px solid var(--surface-card);
}
.kf-avatar img{ width:100%; height:100%; object-fit:cover; border-radius:0; }
.kf-avatar--xs{ width:24px; height:24px; font-size:10px; }
.kf-avatar--sm{ width:32px; height:32px; font-size:12px; }
.kf-avatar--md{ width:44px; height:44px; font-size:15px; }
.kf-avatar--lg{ width:64px; height:64px; font-size:22px; }
.kf-avatar--accent{ background:var(--brand-accent); color:var(--brand-on-accent); }
.kf-avatar--indigo{ background:var(--kipp-indigo); color:var(--kipp-white); }
.kf-avatargroup{ display:inline-flex; }
.kf-avatargroup > .kf-avatar:not(:first-child){ margin-left:-10px; }
`;
function initials(name = '') {
  return name.trim().split(/\s+/).slice(0, 2).map(p => p[0] || '').join('');
}

/**
 * Avatar — circular person/initials chip.
 */
function Avatar({
  src = null,
  name = '',
  size = 'md',
  tone = 'default',
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-avatar', CSS);
  const cls = ['kf-avatar', `kf-avatar--${size}`, tone !== 'default' ? `kf-avatar--${tone}` : '', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls,
    title: name
  }, rest), src ? /*#__PURE__*/React.createElement("img", {
    src: src,
    alt: name
  }) : initials(name));
}

/** AvatarGroup — overlapping stack of avatars. */
function AvatarGroup({
  children,
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-avatar', CSS);
  return /*#__PURE__*/React.createElement("span", _extends({
    className: ['kf-avatargroup', className].filter(Boolean).join(' ')
  }, rest), children);
}
Object.assign(__ds_scope, { Avatar, AvatarGroup });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Avatar.jsx", error: String((e && e.message) || e) }); }

// components/display/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-badge{
  display:inline-flex; align-items:center; gap:5px;
  font-family:var(--font-brand); font-weight:700; text-transform:uppercase; letter-spacing:.05em;
  font-size:11px; line-height:1; padding:5px 9px; border-radius:var(--radius-pill);
  background:var(--neutral-100); color:var(--text-body); white-space:nowrap;
}
.kf-badge .kf-badge__dot{ width:6px; height:6px; border-radius:var(--radius-pill); background:currentColor; }
.kf-badge--neutral{ background:var(--neutral-100); color:var(--neutral-700); }
.kf-badge--indigo{ background:var(--indigo-100); color:var(--indigo-700); }
.kf-badge--success{ background:var(--status-success-surface); color:var(--green-700); }
.kf-badge--warning{ background:var(--status-warning-surface); color:var(--orange-700); }
.kf-badge--danger{ background:var(--status-danger-surface); color:var(--red-700); }
.kf-badge--info{ background:var(--status-info-surface); color:var(--blue-700); }
.kf-badge--solid{ background:var(--kipp-indigo); color:var(--kipp-white); }
.kf-badge--accent{ background:var(--brand-accent); color:var(--brand-on-accent); }
`;

/**
 * Badge — small status / category pill.
 */
function Badge({
  children,
  tone = 'neutral',
  dot = false,
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-badge', CSS);
  const cls = ['kf-badge', `kf-badge--${tone}`, className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls
  }, rest), dot && /*#__PURE__*/React.createElement("span", {
    className: "kf-badge__dot"
  }), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Badge.jsx", error: String((e && e.message) || e) }); }

// components/display/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-card{
  background:var(--surface-card);
  border:var(--border-width) solid var(--border-subtle);
  border-radius:var(--radius-lg);
  overflow:hidden;
  transition:box-shadow var(--dur-base) var(--ease-standard), transform var(--dur-base) var(--ease-standard);
}
.kf-card--pad{ padding:var(--pad-card); }
.kf-card--sm{ box-shadow:var(--shadow-sm); }
.kf-card--md{ box-shadow:var(--shadow-md); }
.kf-card--lg{ box-shadow:var(--shadow-lg); }
.kf-card--flat{ box-shadow:none; }
.kf-card--pop{ border:var(--border-width-strong) solid var(--kipp-indigo); box-shadow:var(--shadow-pop); border-radius:var(--radius-md); }
.kf-card--inverse{ background:var(--kipp-indigo); border-color:transparent; color:var(--text-inverse); }
.kf-card--accentbar{ border-top:5px solid var(--brand-accent); }
.kf-card--interactive{ cursor:pointer; }
.kf-card--interactive:hover{ box-shadow:var(--shadow-lg); transform:translateY(-3px); }
`;

/**
 * Card — the base surface container. Square-ish, bold, lightly raised.
 */
function Card({
  children,
  elevation = 'sm',
  pad = true,
  pop = false,
  inverse = false,
  accentBar = false,
  interactive = false,
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-card', CSS);
  const cls = ['kf-card', pop ? 'kf-card--pop' : `kf-card--${elevation}`, pad ? 'kf-card--pad' : '', inverse ? 'kf-card--inverse' : '', accentBar ? 'kf-card--accentbar' : '', interactive ? 'kf-card--interactive' : '', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("div", _extends({
    className: cls
  }, rest), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Card.jsx", error: String((e && e.message) || e) }); }

// components/display/StatCallout.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-stat{ display:flex; flex-direction:column; gap:4px; }
.kf-stat__value{
  font-family:var(--font-mono); font-variant-numeric:tabular-nums;
  font-weight:700; line-height:1; color:var(--text-strong); letter-spacing:-.01em;
}
.kf-stat--sm .kf-stat__value{ font-size:30px; }
.kf-stat--md .kf-stat__value{ font-size:44px; }
.kf-stat--lg .kf-stat__value{ font-size:64px; }
.kf-stat--accent .kf-stat__value{ color:var(--brand-accent); }
.kf-stat--inverse .kf-stat__value{ color:var(--kipp-white); }
.kf-stat__label{
  font-family:var(--font-brand); font-weight:700; text-transform:uppercase;
  letter-spacing:.06em; font-size:12px; color:var(--text-muted);
}
.kf-stat--inverse .kf-stat__label{ color:var(--indigo-200); }
.kf-stat__sub{ font-family:var(--font-sans); font-size:13px; color:var(--text-muted); }
.kf-stat--inverse .kf-stat__sub{ color:var(--indigo-200); }
.kf-stat__trend{ display:inline-flex; align-items:center; gap:4px; font-family:var(--font-sans); font-weight:600; font-size:13px; }
.kf-stat__trend--up{ color:var(--green-700); }
.kf-stat__trend--down{ color:var(--red-700); }
`;

/**
 * StatCallout — the brand's signature big-number metric block.
 */
function StatCallout({
  value,
  label,
  sub = null,
  size = 'md',
  tone = 'default',
  trend = null,
  // { dir: 'up'|'down', text: '+4.2 pts' }
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-stat', CSS);
  const cls = ['kf-stat', `kf-stat--${size}`, `kf-stat--${tone}`, className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("div", _extends({
    className: cls
  }, rest), label && /*#__PURE__*/React.createElement("span", {
    className: "kf-stat__label"
  }, label), /*#__PURE__*/React.createElement("span", {
    className: "kf-stat__value"
  }, value), trend && /*#__PURE__*/React.createElement("span", {
    className: `kf-stat__trend kf-stat__trend--${trend.dir}`
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "13",
    height: "13",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2.2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round"
  }, trend.dir === 'up' ? /*#__PURE__*/React.createElement("path", {
    d: "M3 11l5-5 5 5"
  }) : /*#__PURE__*/React.createElement("path", {
    d: "M3 5l5 5 5-5"
  })), trend.text), sub && /*#__PURE__*/React.createElement("span", {
    className: "kf-stat__sub"
  }, sub));
}
Object.assign(__ds_scope, { StatCallout });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/StatCallout.jsx", error: String((e && e.message) || e) }); }

// components/display/Tag.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-tag{
  display:inline-flex; align-items:center; gap:6px;
  font-family:var(--font-sans); font-weight:600; font-size:13px; line-height:1;
  padding:7px 12px; border-radius:var(--radius-pill);
  background:var(--surface-card); color:var(--text-body);
  border:var(--border-width) solid var(--border-default); cursor:default;
  transition:background var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
}
.kf-tag--selectable{ cursor:pointer; }
.kf-tag--selectable:hover{ border-color:var(--kipp-indigo); }
.kf-tag--selected{ background:var(--kipp-indigo); border-color:var(--kipp-indigo); color:var(--kipp-white); }
.kf-tag__x{ display:inline-flex; align-items:center; cursor:pointer; opacity:.55; }
.kf-tag__x:hover{ opacity:1; }
.kf-tag__dot{ width:8px; height:8px; border-radius:var(--radius-pill); flex:none; }
`;

/**
 * Tag — filter / category chip; selectable and removable variants.
 */
function Tag({
  children,
  selected = false,
  selectable = false,
  dotColor = null,
  onRemove = null,
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-tag', CSS);
  const cls = ['kf-tag', selectable ? 'kf-tag--selectable' : '', selected ? 'kf-tag--selected' : '', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls
  }, rest), dotColor && /*#__PURE__*/React.createElement("span", {
    className: "kf-tag__dot",
    style: {
      background: dotColor
    }
  }), children, onRemove && /*#__PURE__*/React.createElement("span", {
    className: "kf-tag__x",
    role: "button",
    "aria-label": "Remove",
    onClick: e => {
      e.stopPropagation();
      onRemove(e);
    }
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "13",
    height: "13",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2",
    "stroke-linecap": "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 4l8 8M12 4l-8 8"
  }))));
}
Object.assign(__ds_scope, { Tag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/display/Tag.jsx", error: String((e && e.message) || e) }); }

// components/forms/Checkbox.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-check{ display:inline-flex; align-items:flex-start; gap:10px; cursor:pointer; font-family:var(--font-sans); font-size:15px; color:var(--text-body); }
.kf-check input{ position:absolute; opacity:0; width:0; height:0; }
.kf-check__box{
  width:20px; height:20px; flex:none; margin-top:1px;
  border:var(--border-width-strong) solid var(--border-default); border-radius:var(--radius-sm);
  background:var(--surface-card); display:inline-flex; align-items:center; justify-content:center;
  transition:background var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard);
}
.kf-check__box svg{ width:14px; height:14px; opacity:0; color:var(--kipp-white); transition:opacity var(--dur-fast) var(--ease-standard); }
.kf-check:hover .kf-check__box{ border-color:var(--kipp-indigo); }
.kf-check input:checked + .kf-check__box{ background:var(--kipp-indigo); border-color:var(--kipp-indigo); }
.kf-check input:checked + .kf-check__box svg{ opacity:1; }
.kf-check input:focus-visible + .kf-check__box{ box-shadow:var(--ring); }
.kf-check--round .kf-check__box{ border-radius:var(--radius-pill); }
.kf-check input:disabled ~ *{ opacity:.5; }
`;

/**
 * Checkbox — labeled boolean control (square, or round for single-choice lists).
 */
function Checkbox({
  label,
  round = false,
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-check', CSS);
  return /*#__PURE__*/React.createElement("label", {
    className: ['kf-check', round ? 'kf-check--round' : '', className].filter(Boolean).join(' ')
  }, /*#__PURE__*/React.createElement("input", _extends({
    type: "checkbox"
  }, rest)), /*#__PURE__*/React.createElement("span", {
    className: "kf-check__box"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2.5",
    "stroke-linecap": "round",
    "stroke-linejoin": "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M3 8.5l3.5 3.5L13 4.5"
  }))), label && /*#__PURE__*/React.createElement("span", {
    className: "kf-check__label"
  }, label));
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-field{ display:flex; flex-direction:column; gap:6px; }
.kf-field__label{ font-family:var(--font-brand); font-weight:700; text-transform:uppercase; letter-spacing:.05em; font-size:12px; color:var(--text-strong); }
.kf-field__req{ color:var(--status-danger); margin-left:2px; }
.kf-input{
  font-family:var(--font-sans); font-size:15px; color:var(--text-body);
  background:var(--surface-card); border:var(--border-width) solid var(--border-default);
  border-radius:var(--radius-md); padding:11px 13px; width:100%;
  transition:border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}
.kf-input::placeholder{ color:var(--text-subtle); }
.kf-input:hover{ border-color:var(--neutral-400); }
.kf-input:focus{ outline:none; border-color:var(--kipp-indigo); box-shadow:var(--ring); }
.kf-input--invalid{ border-color:var(--status-danger); }
.kf-input--invalid:focus{ box-shadow:0 0 0 3px var(--red-200); }
.kf-input:disabled{ background:var(--surface-muted); color:var(--text-subtle); cursor:not-allowed; }
.kf-field__hint{ font-family:var(--font-sans); font-size:12.5px; color:var(--text-muted); }
.kf-field__hint--err{ color:var(--status-danger); }
.kf-input__wrap{ position:relative; display:flex; align-items:center; }
.kf-input__icon{ position:absolute; left:12px; display:flex; color:var(--text-subtle); pointer-events:none; }
.kf-input__icon ~ .kf-input{ padding-left:38px; }
`;

/**
 * Input — labeled text field with hint / error states.
 */
function Input({
  label,
  hint = null,
  error = null,
  required = false,
  icon = null,
  id,
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-input', CSS);
  const fieldId = id || (label ? `kf-${String(label).toLowerCase().replace(/\s+/g, '-')}` : undefined);
  const invalid = Boolean(error);
  return /*#__PURE__*/React.createElement("div", {
    className: ['kf-field', className].filter(Boolean).join(' ')
  }, label && /*#__PURE__*/React.createElement("label", {
    className: "kf-field__label",
    htmlFor: fieldId
  }, label, required && /*#__PURE__*/React.createElement("span", {
    className: "kf-field__req"
  }, "*")), /*#__PURE__*/React.createElement("span", {
    className: "kf-input__wrap"
  }, icon && /*#__PURE__*/React.createElement("span", {
    className: "kf-input__icon"
  }, icon), /*#__PURE__*/React.createElement("input", _extends({
    id: fieldId,
    className: ['kf-input', invalid ? 'kf-input--invalid' : ''].filter(Boolean).join(' '),
    "aria-invalid": invalid
  }, rest))), error ? /*#__PURE__*/React.createElement("span", {
    className: "kf-field__hint kf-field__hint--err"
  }, error) : hint ? /*#__PURE__*/React.createElement("span", {
    className: "kf-field__hint"
  }, hint) : null);
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-select__wrap{ position:relative; display:flex; align-items:center; }
.kf-select{
  appearance:none; -webkit-appearance:none;
  font-family:var(--font-sans); font-size:15px; color:var(--text-body);
  background:var(--surface-card); border:var(--border-width) solid var(--border-default);
  border-radius:var(--radius-md); padding:11px 38px 11px 13px; width:100%; cursor:pointer;
  transition:border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}
.kf-select:hover{ border-color:var(--neutral-400); }
.kf-select:focus{ outline:none; border-color:var(--kipp-indigo); box-shadow:var(--ring); }
.kf-select:disabled{ background:var(--surface-muted); color:var(--text-subtle); cursor:not-allowed; }
.kf-select__chev{ position:absolute; right:13px; pointer-events:none; color:var(--text-muted); display:flex; }
`;

/**
 * Select — labeled native dropdown styled to match Input.
 */
function Select({
  label,
  hint = null,
  required = false,
  options = [],
  // [{value,label}] or string[]
  placeholder = null,
  id,
  className = '',
  children,
  ...rest
}) {
  __ds_scope.useDSStyle('kf-select', CSS);
  const fieldId = id || (label ? `kf-sel-${String(label).toLowerCase().replace(/\s+/g, '-')}` : undefined);
  const opts = options.map(o => typeof o === 'string' ? {
    value: o,
    label: o
  } : o);
  return /*#__PURE__*/React.createElement("div", {
    className: ['kf-field', className].filter(Boolean).join(' ')
  }, label && /*#__PURE__*/React.createElement("label", {
    className: "kf-field__label",
    htmlFor: fieldId
  }, label, required && /*#__PURE__*/React.createElement("span", {
    className: "kf-field__req"
  }, "*")), /*#__PURE__*/React.createElement("span", {
    className: "kf-select__wrap"
  }, /*#__PURE__*/React.createElement("select", _extends({
    id: fieldId,
    className: "kf-select"
  }, rest), placeholder && /*#__PURE__*/React.createElement("option", {
    value: "",
    disabled: true
  }, placeholder), opts.map(o => /*#__PURE__*/React.createElement("option", {
    key: o.value,
    value: o.value
  }, o.label)), children), /*#__PURE__*/React.createElement("span", {
    className: "kf-select__chev"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "16",
    height: "16",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 6l4 4 4-4"
  })))), hint && /*#__PURE__*/React.createElement("span", {
    className: "kf-field__hint"
  }, hint));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/forms/Switch.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-switch{ display:inline-flex; align-items:center; gap:10px; cursor:pointer; font-family:var(--font-sans); font-size:15px; color:var(--text-body); }
.kf-switch input{ position:absolute; opacity:0; width:0; height:0; }
.kf-switch__track{
  width:42px; height:24px; flex:none; border-radius:var(--radius-pill);
  background:var(--neutral-300); position:relative;
  transition:background var(--dur-base) var(--ease-standard);
}
.kf-switch__thumb{
  position:absolute; top:3px; left:3px; width:18px; height:18px; border-radius:var(--radius-pill);
  background:var(--kipp-white); box-shadow:var(--shadow-sm);
  transition:transform var(--dur-base) var(--ease-spring);
}
.kf-switch input:checked + .kf-switch__track{ background:var(--status-success); }
.kf-switch input:checked + .kf-switch__track .kf-switch__thumb{ transform:translateX(18px); }
.kf-switch input:focus-visible + .kf-switch__track{ box-shadow:var(--ring); }
.kf-switch input:disabled + .kf-switch__track{ opacity:.5; }
`;

/**
 * Switch — labeled on/off toggle.
 */
function Switch({
  label,
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-switch', CSS);
  return /*#__PURE__*/React.createElement("label", {
    className: ['kf-switch', className].filter(Boolean).join(' ')
  }, /*#__PURE__*/React.createElement("input", _extends({
    type: "checkbox",
    role: "switch"
  }, rest)), /*#__PURE__*/React.createElement("span", {
    className: "kf-switch__track"
  }, /*#__PURE__*/React.createElement("span", {
    className: "kf-switch__thumb"
  })), label && /*#__PURE__*/React.createElement("span", {
    className: "kf-switch__label"
  }, label));
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Switch.jsx", error: String((e && e.message) || e) }); }

// components/navigation/SegmentedControl.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-seg{ display:inline-flex; background:var(--surface-muted); border-radius:var(--radius-md); padding:4px; gap:2px; }
.kf-seg__opt{
  appearance:none; border:none; cursor:pointer; background:transparent;
  font-family:var(--font-brand); font-weight:700; text-transform:uppercase; letter-spacing:.04em;
  font-size:12px; color:var(--text-muted); padding:8px 16px; border-radius:var(--radius-sm);
  transition:background var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}
.kf-seg__opt:hover{ color:var(--text-strong); }
.kf-seg__opt--active{ background:var(--surface-card); color:var(--text-strong); box-shadow:var(--shadow-sm); }
.kf-seg__opt:focus-visible{ outline:none; box-shadow:var(--ring); }
`;

/**
 * SegmentedControl — compact 2–4 option switch for tight toolbars.
 */
function SegmentedControl({
  options = [],
  value,
  onChange = () => {},
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-seg', CSS);
  const items = options.map(o => typeof o === 'string' ? {
    value: o,
    label: o
  } : o);
  const active = value ?? items[0]?.value;
  return /*#__PURE__*/React.createElement("div", _extends({
    className: ['kf-seg', className].filter(Boolean).join(' '),
    role: "group"
  }, rest), items.map(o => /*#__PURE__*/React.createElement("button", {
    key: o.value,
    className: ['kf-seg__opt', o.value === active ? 'kf-seg__opt--active' : ''].filter(Boolean).join(' '),
    "aria-pressed": o.value === active,
    onClick: () => onChange(o.value)
  }, o.label)));
}
Object.assign(__ds_scope, { SegmentedControl });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/SegmentedControl.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.kf-tabs{ display:flex; gap:4px; border-bottom:var(--border-width-strong) solid var(--border-subtle); }
.kf-tab{
  appearance:none; border:none; background:none; cursor:pointer;
  font-family:var(--font-brand); font-weight:700; text-transform:uppercase; letter-spacing:.04em;
  font-size:13px; color:var(--text-muted); padding:12px 16px; position:relative;
  transition:color var(--dur-fast) var(--ease-standard);
}
.kf-tab:hover{ color:var(--text-strong); }
.kf-tab::after{
  content:''; position:absolute; left:0; right:0; bottom:-2px; height:3px;
  background:var(--brand-accent); border-radius:var(--radius-pill) var(--radius-pill) 0 0;
  transform:scaleX(0); transform-origin:center; transition:transform var(--dur-base) var(--ease-out);
}
.kf-tab--active{ color:var(--text-strong); }
.kf-tab--active::after{ transform:scaleX(1); }
.kf-tab:focus-visible{ outline:none; box-shadow:var(--ring); border-radius:var(--radius-sm); }
`;

/**
 * Tabs — underline tab bar. Controlled via value / onChange.
 */
function Tabs({
  tabs = [],
  // [{value,label}] or string[]
  value,
  onChange = () => {},
  className = '',
  ...rest
}) {
  __ds_scope.useDSStyle('kf-tabs', CSS);
  const items = tabs.map(t => typeof t === 'string' ? {
    value: t,
    label: t
  } : t);
  const active = value ?? items[0]?.value;
  return /*#__PURE__*/React.createElement("div", _extends({
    className: ['kf-tabs', className].filter(Boolean).join(' '),
    role: "tablist"
  }, rest), items.map(t => /*#__PURE__*/React.createElement("button", {
    key: t.value,
    role: "tab",
    "aria-selected": t.value === active,
    className: ['kf-tab', t.value === active ? 'kf-tab--active' : ''].filter(Boolean).join(' '),
    onClick: () => onChange(t.value)
  }, t.label)));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// ui_kits/data-dashboard/Charts.jsx
try { (() => {
const {
  Card
} = window.KIPPNJMiamiDesignSystem_1916b9;

// ---- Grouped bar chart: proficiency by grade band ----
function BarChart() {
  const data = [{
    label: 'Grade 3',
    kipp: 64,
    district: 41
  }, {
    label: 'Grade 4',
    kipp: 71,
    district: 45
  }, {
    label: 'Grade 5',
    kipp: 68,
    district: 43
  }, {
    label: 'Grade 6',
    kipp: 75,
    district: 47
  }, {
    label: 'Grade 7',
    kipp: 79,
    district: 49
  }, {
    label: 'Grade 8',
    kipp: 82,
    district: 51
  }];
  return /*#__PURE__*/React.createElement(Card, {
    elevation: "sm"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      marginBottom: 18
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "kf-eyebrow"
  }, "ELA proficiency"), /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 18,
      color: 'var(--text-strong)',
      marginTop: 4
    }
  }, "% meeting / exceeding by grade")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Legend, {
    color: "var(--viz-1)",
    label: "KIPP"
  }), /*#__PURE__*/React.createElement(Legend, {
    color: "var(--neutral-300)",
    label: "District avg"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      gap: 18,
      height: 200,
      paddingTop: 10
    }
  }, data.map(d => /*#__PURE__*/React.createElement("div", {
    key: d.label,
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      gap: 5,
      height: 168,
      width: '100%',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement(Bar, {
    pct: d.kipp,
    color: "var(--viz-1)"
  }), /*#__PURE__*/React.createElement(Bar, {
    pct: d.district,
    color: "var(--neutral-300)"
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 12,
      color: 'var(--text-muted)'
    }
  }, d.label)))));
}
function Bar({
  pct,
  color
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width: 18,
      height: `${pct}%`,
      background: color,
      borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      top: -17,
      left: '50%',
      transform: 'translateX(-50%)',
      fontFamily: 'var(--font-mono)',
      fontSize: 10.5,
      fontWeight: 700,
      color: 'var(--text-muted)'
    }
  }, pct));
}
function Legend({
  color,
  label
}) {
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      fontFamily: 'var(--font-sans)',
      fontSize: 12,
      color: 'var(--text-muted)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 11,
      height: 11,
      borderRadius: 3,
      background: color
    }
  }), label);
}

// ---- Donut: enrollment by grade band ----
function Donut() {
  const segs = [{
    label: 'Elementary',
    value: 42,
    color: 'var(--viz-1)'
  }, {
    label: 'Middle',
    value: 34,
    color: 'var(--viz-2)'
  }, {
    label: 'High',
    value: 24,
    color: 'var(--viz-3)'
  }];
  let acc = 0;
  const stops = segs.map(s => {
    const start = acc;
    acc += s.value;
    return `${s.color} ${start}% ${acc}%`;
  }).join(', ');
  return /*#__PURE__*/React.createElement(Card, {
    elevation: "sm"
  }, /*#__PURE__*/React.createElement("span", {
    className: "kf-eyebrow"
  }, "Enrollment mix"), /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 18,
      color: 'var(--text-strong)',
      marginTop: 4,
      marginBottom: 18
    }
  }, "Students by grade band"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 24
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 130,
      height: 130,
      borderRadius: '50%',
      flex: 'none',
      background: `conic-gradient(${stops})`,
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 26,
      background: 'var(--surface-card)',
      borderRadius: '50%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      fontSize: 22,
      color: 'var(--text-strong)'
    }
  }, "9.0k"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 10.5,
      color: 'var(--text-muted)'
    }
  }, "students"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gap: 10,
      flex: 1
    }
  }, segs.map(s => /*#__PURE__*/React.createElement("div", {
    key: s.label,
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      fontFamily: 'var(--font-sans)',
      fontSize: 13.5,
      color: 'var(--text-body)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 11,
      height: 11,
      borderRadius: 3,
      background: s.color
    }
  }), s.label), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      fontSize: 14,
      color: 'var(--text-strong)'
    }
  }, s.value, "%"))))));
}
window.BarChart = BarChart;
window.Donut = Donut;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/data-dashboard/Charts.jsx", error: String((e && e.message) || e) }); }

// ui_kits/data-dashboard/DashBody.jsx
try { (() => {
const {
  StatCallout,
  Card
} = window.KIPPNJMiamiDesignSystem_1916b9;
function KpiRow() {
  const kpis = [{
    value: '9,042',
    label: 'Students enrolled',
    trend: {
      dir: 'up',
      text: '+218 YoY'
    }
  }, {
    value: '93.4%',
    label: 'Avg daily attendance',
    trend: {
      dir: 'up',
      text: '+1.2 pts'
    }
  }, {
    value: '74%',
    label: 'ELA proficiency',
    trend: {
      dir: 'up',
      text: '+5 pts'
    }
  }, {
    value: '95.2%',
    label: 'College enrollment',
    trend: {
      dir: 'up',
      text: '+3.1 pts'
    }
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 'var(--space-5)'
    }
  }, kpis.map(k => /*#__PURE__*/React.createElement(Card, {
    key: k.label,
    elevation: "sm"
  }, /*#__PURE__*/React.createElement(StatCallout, {
    value: k.value,
    label: k.label,
    size: "md",
    trend: k.trend
  }))));
}
function DashBody({
  section
}) {
  const titles = {
    overview: 'Network overview',
    academics: 'Academics',
    attendance: 'Attendance',
    enrollment: 'Enrollment',
    staff: 'Staff & culture'
  };
  return /*#__PURE__*/React.createElement("main", {
    style: {
      flex: 1,
      padding: 'var(--space-8)',
      background: 'var(--surface-page)',
      overflow: 'auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 'var(--space-6)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "kf-eyebrow"
  }, "2025\u201326 school year"), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 800,
      fontSize: 32,
      letterSpacing: '-.01em',
      color: 'var(--text-strong)',
      marginTop: 4
    }
  }, titles[section])), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gap: 'var(--space-6)'
    }
  }, /*#__PURE__*/React.createElement(KpiRow, null), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1.5fr 1fr',
      gap: 'var(--space-6)'
    }
  }, /*#__PURE__*/React.createElement(window.BarChart, null), /*#__PURE__*/React.createElement(window.Donut, null)), /*#__PURE__*/React.createElement(window.DataTable, null)));
}
window.DashBody = DashBody;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/data-dashboard/DashBody.jsx", error: String((e && e.message) || e) }); }

// ui_kits/data-dashboard/DashSidebar.jsx
try { (() => {
const {
  Avatar
} = window.KIPPNJMiamiDesignSystem_1916b9;
const NAV = [{
  id: 'overview',
  label: 'Overview',
  icon: 'M3 12l9-9 9 9M5 10v10h14V10'
}, {
  id: 'academics',
  label: 'Academics',
  icon: 'M4 19V5h16v14M4 12h16'
}, {
  id: 'attendance',
  label: 'Attendance',
  icon: 'M8 2v4M16 2v4M3 9h18M5 5h14v15H5z'
}, {
  id: 'enrollment',
  label: 'Enrollment',
  icon: 'M16 21v-2a4 4 0 0 0-8 0v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z'
}, {
  id: 'staff',
  label: 'Staff & culture',
  icon: 'M17 21v-2a4 4 0 0 0-3-3.9M9 21v-2a4 4 0 0 0-4-4H5M12 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6z'
}];
function DashSidebar({
  active,
  onNav
}) {
  return /*#__PURE__*/React.createElement("aside", {
    style: {
      width: 244,
      flex: 'none',
      background: 'var(--kipp-indigo)',
      color: '#fff',
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      position: 'sticky',
      top: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '20px 20px 18px',
      borderBottom: '1px solid rgba(255,255,255,.12)'
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-white-trimmed.png",
    alt: "KIPP NJ | Miami Data",
    style: {
      height: 30
    }
  })), /*#__PURE__*/React.createElement("nav", {
    style: {
      padding: 12,
      display: 'grid',
      gap: 2,
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 10,
      textTransform: 'uppercase',
      letterSpacing: '.12em',
      color: 'var(--indigo-300)',
      padding: '10px 12px 6px'
    }
  }, "Network data"), NAV.map(n => {
    const on = n.id === active;
    return /*#__PURE__*/React.createElement("button", {
      key: n.id,
      onClick: () => onNav(n.id),
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        width: '100%',
        textAlign: 'left',
        background: on ? 'rgba(255,255,255,.12)' : 'transparent',
        border: 'none',
        cursor: 'pointer',
        padding: '11px 12px',
        borderRadius: 'var(--radius-md)',
        color: on ? '#fff' : 'var(--indigo-100)',
        fontFamily: 'var(--font-brand)',
        fontWeight: 600,
        fontSize: 13.5,
        letterSpacing: '.01em',
        borderLeft: on ? '3px solid var(--brand-accent)' : '3px solid transparent'
      }
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "18",
      height: "18",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.9",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, /*#__PURE__*/React.createElement("path", {
      d: n.icon
    })), n.label);
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 14,
      borderTop: '1px solid rgba(255,255,255,.12)',
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: "Data Team",
    tone: "accent",
    size: "sm"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      lineHeight: 1.2
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 13,
      color: '#fff'
    }
  }, "Data Team"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 11.5,
      color: 'var(--indigo-300)'
    }
  }, "Research & Analytics"))));
}
window.DashSidebar = DashSidebar;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/data-dashboard/DashSidebar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/data-dashboard/DashTopbar.jsx
try { (() => {
const {
  SegmentedControl,
  Button
} = window.KIPPNJMiamiDesignSystem_1916b9;
const SCHOOLS = ['Network — all schools', 'KIPP Rise Academy', 'KIPP Newark Collegiate', 'KIPP Cooper Norcross', 'KIPP Miami Prep'];
function DashTopbar({
  school,
  onSchool,
  range,
  onRange
}) {
  const [open, setOpen] = React.useState(false);
  return /*#__PURE__*/React.createElement("header", {
    style: {
      height: 68,
      flex: 'none',
      background: 'var(--surface-card)',
      borderBottom: '1px solid var(--border-subtle)',
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--space-5)',
      padding: '0 var(--space-8)',
      position: 'sticky',
      top: 0,
      zIndex: 30
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setOpen(o => !o),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      cursor: 'pointer',
      background: 'var(--surface-sunken)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)',
      padding: '9px 14px',
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 14,
      color: 'var(--text-strong)'
    }
  }, school, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "14",
    height: "14",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 6l4 4 4-4"
  }))), open && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 'calc(100% + 6px)',
      left: 0,
      minWidth: 260,
      background: '#fff',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-lg)',
      padding: 6,
      zIndex: 40
    }
  }, SCHOOLS.map(s => /*#__PURE__*/React.createElement("button", {
    key: s,
    onClick: () => {
      onSchool(s);
      setOpen(false);
    },
    style: {
      display: 'block',
      width: '100%',
      textAlign: 'left',
      cursor: 'pointer',
      background: s === school ? 'var(--indigo-50)' : 'transparent',
      border: 'none',
      padding: '9px 12px',
      borderRadius: 'var(--radius-sm)',
      fontFamily: 'var(--font-sans)',
      fontSize: 14,
      color: s === school ? 'var(--kipp-indigo)' : 'var(--text-body)',
      fontWeight: s === school ? 700 : 400
    }
  }, s)))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--space-4)'
    }
  }, /*#__PURE__*/React.createElement(SegmentedControl, {
    value: range,
    onChange: onRange,
    options: [{
      value: 'q',
      label: 'Quarter'
    }, {
      value: 'ytd',
      label: 'YTD'
    }, {
      value: 'multi',
      label: 'Multi-yr'
    }]
  }), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "sm",
    iconLeft: /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "15",
      height: "15",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "2",
      strokeLinecap: "round",
      strokeLinejoin: "round"
    }, /*#__PURE__*/React.createElement("path", {
      d: "M12 3v12M7 10l5 5 5-5M5 21h14"
    }))
  }, "Export")));
}
window.DashTopbar = DashTopbar;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/data-dashboard/DashTopbar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/data-dashboard/DataTable.jsx
try { (() => {
const {
  Card,
  Badge,
  StatCallout
} = window.KIPPNJMiamiDesignSystem_1916b9;
const ROWS = [{
  school: 'KIPP Rise Academy',
  region: 'Newark',
  band: '5–8',
  ela: 79,
  math: 74,
  att: 94.2,
  trend: 'up'
}, {
  school: 'KIPP Newark Collegiate',
  region: 'Newark',
  band: '9–12',
  ela: 71,
  math: 68,
  att: 92.8,
  trend: 'up'
}, {
  school: 'KIPP Cooper Norcross',
  region: 'Camden',
  band: '5–8',
  ela: 66,
  math: 70,
  att: 93.5,
  trend: 'flat'
}, {
  school: 'KIPP Paterson Prep',
  region: 'Paterson',
  band: '5–8',
  ela: 72,
  math: 69,
  att: 91.4,
  trend: 'up'
}, {
  school: 'KIPP Miami Prep',
  region: 'Miami',
  band: '5–8',
  ela: 75,
  math: 73,
  att: 95.1,
  trend: 'up'
}];
const regionTone = {
  Newark: 'info',
  Camden: 'success',
  Paterson: 'danger',
  Miami: 'warning'
};
function DataTable() {
  return /*#__PURE__*/React.createElement(Card, {
    elevation: "sm",
    pad: false
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '18px var(--space-6) 14px',
      borderBottom: '1px solid var(--border-subtle)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "kf-eyebrow"
  }, "School comparison"), /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 18,
      color: 'var(--text-strong)',
      marginTop: 4
    }
  }, "Performance by school")), /*#__PURE__*/React.createElement("table", {
    style: {
      width: '100%',
      borderCollapse: 'collapse'
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, ['School', 'Region', 'Band', 'ELA', 'Math', 'Attendance', ''].map((h, i) => /*#__PURE__*/React.createElement("th", {
    key: h + i,
    style: {
      textAlign: i > 2 && i < 6 ? 'right' : 'left',
      padding: '11px var(--space-6)',
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 11,
      textTransform: 'uppercase',
      letterSpacing: '.06em',
      color: 'var(--text-muted)',
      background: 'var(--surface-sunken)',
      borderBottom: '1px solid var(--border-subtle)',
      whiteSpace: 'nowrap'
    }
  }, h)))), /*#__PURE__*/React.createElement("tbody", null, ROWS.map(r => /*#__PURE__*/React.createElement("tr", {
    key: r.school,
    style: {
      borderBottom: '1px solid var(--divider)'
    }
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '13px var(--space-6)',
      fontFamily: 'var(--font-sans)',
      fontWeight: 600,
      fontSize: 14,
      color: 'var(--text-strong)'
    }
  }, r.school), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '13px var(--space-6)'
    }
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: regionTone[r.region]
  }, r.region)), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '13px var(--space-6)',
      fontFamily: 'var(--font-sans)',
      fontSize: 13.5,
      color: 'var(--text-muted)'
    }
  }, r.band), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '13px var(--space-6)',
      textAlign: 'right',
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      fontSize: 14,
      color: 'var(--text-strong)'
    }
  }, r.ela, "%"), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '13px var(--space-6)',
      textAlign: 'right',
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      fontSize: 14,
      color: 'var(--text-strong)'
    }
  }, r.math, "%"), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '13px var(--space-6)',
      textAlign: 'right',
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      fontSize: 14,
      color: 'var(--text-strong)'
    }
  }, r.att, "%"), /*#__PURE__*/React.createElement("td", {
    style: {
      padding: '13px var(--space-6)',
      textAlign: 'center',
      width: 40
    }
  }, r.trend === 'up' ? /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "16",
    height: "16",
    fill: "none",
    stroke: "var(--green-700)",
    strokeWidth: "2.4",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M3 11l5-5 5 5"
  })) : /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "16",
    height: "16",
    fill: "none",
    stroke: "var(--text-subtle)",
    strokeWidth: "2.4",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M3 8h10"
  }))))))));
}
window.DataTable = DataTable;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/data-dashboard/DataTable.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/ApplyModal.jsx
try { (() => {
const {
  Input,
  Select,
  Button
} = window.KIPPNJMiamiDesignSystem_1916b9;
function ApplyModal({
  region,
  onClose
}) {
  const [done, setDone] = React.useState(false);
  const regionName = {
    newark: 'Newark',
    camden: 'Camden',
    paterson: 'Paterson',
    miami: 'Miami'
  }[region];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 100,
      background: 'rgba(0,18,60,.55)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 20
    },
    onClick: onClose
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      width: 'min(520px, 100%)',
      background: '#fff',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-xl)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--kipp-indigo)',
      padding: 'var(--space-6)',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 11,
      textTransform: 'uppercase',
      letterSpacing: '.1em',
      color: 'var(--brand-accent)'
    }
  }, "KIPP ", regionName), /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 22,
      color: '#fff',
      marginTop: 4
    }
  }, "Start your application")), /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    "aria-label": "Close",
    style: {
      background: 'rgba(255,255,255,.12)',
      border: 'none',
      color: '#fff',
      width: 36,
      height: 36,
      borderRadius: 'var(--radius-md)',
      cursor: 'pointer',
      fontSize: 18
    }
  }, "\xD7")), done ? /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 'var(--space-12) var(--space-8)',
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 64,
      height: 64,
      borderRadius: '50%',
      background: 'var(--status-success-surface)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      margin: '0 auto 16px'
    }
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    width: "32",
    height: "32",
    fill: "none",
    stroke: "var(--green-700)",
    strokeWidth: "2.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M5 13l4 4L19 7"
  }))), /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 22,
      color: 'var(--text-strong)'
    }
  }, "You're all set!"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 15,
      color: 'var(--text-muted)',
      marginTop: 8,
      maxWidth: '34ch',
      marginInline: 'auto'
    }
  }, "Our enrollment team will reach out within two business days to finish your ", regionName, " application."), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 24
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "accent",
    onClick: onClose
  }, "Done"))) : /*#__PURE__*/React.createElement("form", {
    style: {
      padding: 'var(--space-6)',
      display: 'grid',
      gap: 'var(--space-4)'
    },
    onSubmit: e => {
      e.preventDefault();
      setDone(true);
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Parent / guardian name",
    placeholder: "Full name",
    required: true
  }), /*#__PURE__*/React.createElement(Input, {
    label: "Email",
    type: "email",
    placeholder: "you@email.com",
    required: true
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 'var(--space-4)'
    }
  }, /*#__PURE__*/React.createElement(Select, {
    label: "Student grade",
    placeholder: "Select grade",
    options: ['Pre-K', 'Kindergarten', 'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8', 'Grade 9']
  }), /*#__PURE__*/React.createElement(Input, {
    label: "ZIP code",
    placeholder: "07102",
    required: true
  })), /*#__PURE__*/React.createElement(Button, {
    type: "submit",
    variant: "accent",
    size: "lg",
    block: true
  }, "Submit application"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 12.5,
      color: 'var(--text-subtle)',
      textAlign: 'center'
    }
  }, "Free to apply. No test required."))));
}
window.ApplyModal = ApplyModal;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/ApplyModal.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/CTABand.jsx
try { (() => {
function CTABand({
  onApply
}) {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: 'var(--brand-accent)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      padding: 'var(--space-16) var(--space-8)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 'var(--space-8)',
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 800,
      fontSize: 36,
      letterSpacing: '-.01em',
      color: 'var(--brand-on-accent)',
      textWrap: 'balance'
    }
  }, "Enrollment is open. Free, public, and close to home."), /*#__PURE__*/React.createElement("p", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 17,
      color: 'var(--brand-on-accent)',
      opacity: .85,
      marginTop: 8
    }
  }, "Apply in minutes \u2014 no test, no tuition, no catch.")), /*#__PURE__*/React.createElement("button", {
    onClick: onApply,
    style: {
      background: 'var(--kipp-indigo)',
      color: '#fff',
      border: 'none',
      borderRadius: 'var(--radius-md)',
      padding: '17px 34px',
      cursor: 'pointer',
      whiteSpace: 'nowrap',
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 16,
      textTransform: 'uppercase',
      letterSpacing: '.04em'
    }
  }, "Start your application")));
}
window.CTABand = CTABand;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/CTABand.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/Hero.jsx
try { (() => {
const {
  PhotoFrame
} = window;
function Hero({
  region,
  onApply
}) {
  const regionName = {
    newark: 'Newark',
    camden: 'Camden',
    paterson: 'Paterson',
    miami: 'Miami'
  }[region];
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: 'var(--kipp-indigo)',
      color: '#fff',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      padding: 'var(--space-20) var(--space-8)',
      display: 'grid',
      gridTemplateColumns: '1.05fr .95fr',
      gap: 'var(--space-16)',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 13,
      textTransform: 'uppercase',
      letterSpacing: '.12em',
      color: 'var(--brand-accent)'
    }
  }, "KIPP ", regionName, " Public Schools"), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 800,
      fontSize: 58,
      lineHeight: 1.02,
      letterSpacing: '-.02em',
      margin: '16px 0 0',
      color: '#fff',
      textWrap: 'balance'
    }
  }, "Our kids will", /*#__PURE__*/React.createElement("br", null), "change the world"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 19,
      lineHeight: 1.55,
      color: 'var(--indigo-100)',
      margin: '20px 0 0',
      maxWidth: '46ch'
    }
  }, "Free, public charter schools preparing students in ", regionName, " for success in college, career, and life \u2014 to and through."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 'var(--space-3)',
      marginTop: 'var(--space-8)'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onApply,
    style: {
      background: 'var(--brand-accent)',
      color: 'var(--brand-on-accent)',
      border: 'none',
      borderRadius: 'var(--radius-md)',
      padding: '15px 30px',
      cursor: 'pointer',
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 15,
      textTransform: 'uppercase',
      letterSpacing: '.04em'
    }
  }, "Enroll your child"), /*#__PURE__*/React.createElement("button", {
    style: {
      background: 'transparent',
      color: '#fff',
      border: '2px solid rgba(255,255,255,.4)',
      borderRadius: 'var(--radius-md)',
      padding: '13px 28px',
      cursor: 'pointer',
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 15,
      textTransform: 'uppercase',
      letterSpacing: '.04em'
    }
  }, "Find a school"))), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement(PhotoFrame, {
    label: "Students",
    ratio: "4 / 3.4",
    tone: "blue",
    style: {
      boxShadow: 'var(--shadow-xl)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      bottom: -22,
      left: -22,
      background: 'var(--brand-accent)',
      color: 'var(--brand-on-accent)',
      padding: '16px 22px',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-lg)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      fontSize: 34,
      lineHeight: 1
    }
  }, "95%"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 11,
      textTransform: 'uppercase',
      letterSpacing: '.06em',
      marginTop: 4
    }
  }, "go to college")))));
}
window.Hero = Hero;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/Hero.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/PhotoFrame.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * PhotoFrame — honest stand-in for brand photography.
 * The brand uses real, warm, candid student/teacher photography with
 * SQUARE corners and no filters. We have no licensed photos in this
 * system, so this renders a labeled placeholder that respects the
 * square-corner rule. Swap for a real <img> in production.
 */
function PhotoFrame({
  label = 'Photography',
  ratio = '4 / 3',
  tone = 'indigo',
  className = '',
  style = {},
  ...rest
}) {
  const bg = {
    indigo: 'var(--indigo-100)',
    blue: 'var(--blue-100)',
    orange: 'var(--orange-100)',
    green: 'var(--green-100)'
  }[tone] || 'var(--indigo-100)';
  const fg = {
    indigo: 'var(--indigo-600)',
    blue: 'var(--blue-700)',
    orange: 'var(--orange-700)',
    green: 'var(--green-700)'
  }[tone] || 'var(--indigo-600)';
  return /*#__PURE__*/React.createElement("div", _extends({
    className: className,
    style: {
      aspectRatio: ratio,
      background: bg,
      borderRadius: 'var(--radius-photo)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: fg,
      overflow: 'hidden',
      position: 'relative',
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    width: "34",
    height: "34",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.6",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      opacity: 0.6
    }
  }, /*#__PURE__*/React.createElement("rect", {
    x: "3",
    y: "5",
    width: "18",
    height: "14",
    rx: "0"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "9",
    cy: "10",
    r: "2"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M3 17l5-4 4 3 3-2 6 5"
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      bottom: 8,
      right: 10,
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 10,
      textTransform: 'uppercase',
      letterSpacing: '.08em',
      opacity: 0.55
    }
  }, label));
}
window.PhotoFrame = PhotoFrame;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/PhotoFrame.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/SchoolFinder.jsx
try { (() => {
const {
  Card,
  Badge,
  Button,
  Tag
} = window.KIPPNJMiamiDesignSystem_1916b9;
const {
  PhotoFrame
} = window;
const SCHOOLS = {
  newark: [{
    name: 'KIPP THRIVE Academy',
    grades: 'K–4',
    band: 'Elementary',
    tone: 'blue',
    seats: 'Now enrolling'
  }, {
    name: 'KIPP Seek Academy',
    grades: 'K–4',
    band: 'Elementary',
    tone: 'blue',
    seats: 'Now enrolling'
  }, {
    name: 'KIPP Rise Academy',
    grades: '5–8',
    band: 'Middle',
    tone: 'green',
    seats: 'Waitlist'
  }, {
    name: 'KIPP Newark Collegiate',
    grades: '9–12',
    band: 'High',
    tone: 'orange',
    seats: 'Now enrolling'
  }],
  camden: [{
    name: 'KIPP Whittier Elementary',
    grades: 'K–4',
    band: 'Elementary',
    tone: 'blue',
    seats: 'Now enrolling'
  }, {
    name: 'KIPP Lanning Square',
    grades: 'K–4',
    band: 'Elementary',
    tone: 'blue',
    seats: 'Now enrolling'
  }, {
    name: 'KIPP Cooper Norcross',
    grades: '5–8',
    band: 'Middle',
    tone: 'green',
    seats: 'Now enrolling'
  }, {
    name: 'KIPP Camden Collegiate',
    grades: '9–12',
    band: 'High',
    tone: 'orange',
    seats: 'Waitlist'
  }],
  paterson: [{
    name: 'KIPP Vista Academy',
    grades: 'K–4',
    band: 'Elementary',
    tone: 'blue',
    seats: 'Now enrolling'
  }, {
    name: 'KIPP Paterson Prep',
    grades: '5–8',
    band: 'Middle',
    tone: 'green',
    seats: 'Now enrolling'
  }, {
    name: 'KIPP Paterson Collegiate',
    grades: '9–12',
    band: 'High',
    tone: 'orange',
    seats: 'Now enrolling'
  }],
  miami: [{
    name: 'KIPP Sunrise Academy',
    grades: 'K–4',
    band: 'Elementary',
    tone: 'blue',
    seats: 'Now enrolling'
  }, {
    name: 'KIPP Liberty Academy',
    grades: 'K–4',
    band: 'Elementary',
    tone: 'blue',
    seats: 'Now enrolling'
  }, {
    name: 'KIPP Miami Prep',
    grades: '5–8',
    band: 'Middle',
    tone: 'green',
    seats: 'Now enrolling'
  }]
};
const FILTERS = ['All', 'Elementary', 'Middle', 'High'];
function SchoolFinder({
  region
}) {
  const [filter, setFilter] = React.useState('All');
  const schools = (SCHOOLS[region] || []).filter(s => filter === 'All' || s.band === filter);
  const regionName = {
    newark: 'Newark',
    camden: 'Camden',
    paterson: 'Paterson',
    miami: 'Miami'
  }[region];
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: 'var(--surface-page)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      padding: 'var(--space-20) var(--space-8)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      marginBottom: 'var(--space-8)',
      flexWrap: 'wrap',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "kf-eyebrow"
  }, "Find a school"), /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 800,
      fontSize: 40,
      letterSpacing: '-.01em',
      margin: '8px 0 0',
      color: 'var(--text-strong)'
    }
  }, "Schools in ", regionName)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8
    }
  }, FILTERS.map(f => /*#__PURE__*/React.createElement(Tag, {
    key: f,
    selectable: true,
    selected: filter === f,
    onClick: () => setFilter(f)
  }, f)))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
      gap: 'var(--space-6)'
    }
  }, schools.map(s => /*#__PURE__*/React.createElement(Card, {
    key: s.name,
    pad: false,
    elevation: "sm",
    interactive: true
  }, /*#__PURE__*/React.createElement(PhotoFrame, {
    label: s.band,
    ratio: "16 / 9",
    tone: s.tone
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 'var(--space-5)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "indigo"
  }, s.grades), /*#__PURE__*/React.createElement(Badge, {
    tone: s.seats === 'Waitlist' ? 'warning' : 'success',
    dot: true
  }, s.seats)), /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 19,
      color: 'var(--text-strong)',
      lineHeight: 1.15
    }
  }, s.name), /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      marginTop: 12,
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 12,
      textTransform: 'uppercase',
      letterSpacing: '.04em',
      color: 'var(--text-link)'
    }
  }, "School details", /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "13",
    height: "13",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2.2"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M6 4l4 4-4 4"
  })))))))));
}
window.SchoolFinder = SchoolFinder;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/SchoolFinder.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/SiteFooter.jsx
try { (() => {
const COLS = [{
  h: 'Schools',
  links: ['Find a school', 'Apply now', 'School calendar', 'Transportation', 'Meals']
}, {
  h: 'Families',
  links: ['Family portal', 'Student support', 'Special education', 'Title I', 'Contact us']
}, {
  h: 'Join our team',
  links: ['Teach with us', 'Open roles', 'Why KIPP', 'Leadership', 'Benefits']
}, {
  h: 'About',
  links: ['Our mission', 'Results', 'News', 'Board', 'Support us']
}];
function SiteFooter() {
  return /*#__PURE__*/React.createElement("footer", {
    style: {
      background: 'var(--indigo-900)',
      color: '#fff'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      padding: 'var(--space-16) var(--space-8) var(--space-10)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1.4fr repeat(4, 1fr)',
      gap: 'var(--space-8)'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-white-trimmed.png",
    alt: "KIPP NJ | Miami",
    style: {
      height: 40
    }
  }), /*#__PURE__*/React.createElement("p", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 14,
      lineHeight: 1.6,
      color: 'var(--indigo-200)',
      marginTop: 16,
      maxWidth: '30ch'
    }
  }, "Free, public charter schools in Newark, Camden, Paterson, and Miami.")), COLS.map(c => /*#__PURE__*/React.createElement("div", {
    key: c.h
  }, /*#__PURE__*/React.createElement("h4", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 12,
      textTransform: 'uppercase',
      letterSpacing: '.08em',
      color: 'var(--brand-accent)',
      marginBottom: 14
    }
  }, c.h), /*#__PURE__*/React.createElement("ul", {
    style: {
      listStyle: 'none',
      margin: 0,
      padding: 0,
      display: 'grid',
      gap: 9
    }
  }, c.links.map(l => /*#__PURE__*/React.createElement("li", {
    key: l
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 14,
      color: 'var(--indigo-100)'
    }
  }, l))))))), /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: '1px solid rgba(255,255,255,.12)',
      marginTop: 'var(--space-12)',
      paddingTop: 'var(--space-6)',
      display: 'flex',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 13,
      color: 'var(--indigo-300)'
    }
  }, "\xA9 2026 KIPP New Jersey & KIPP Miami. All rights reserved."), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 13,
      color: 'var(--indigo-300)'
    }
  }, "Privacy \xB7 Accessibility \xB7 Non-discrimination"))));
}
window.SiteFooter = SiteFooter;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/SiteFooter.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/SiteHeader.jsx
try { (() => {
const NAV = ['Our Schools', 'Apply', 'Academics', 'Careers', 'About'];
const REGIONS = [{
  id: 'newark',
  label: 'Newark'
}, {
  id: 'camden',
  label: 'Camden'
}, {
  id: 'paterson',
  label: 'Paterson'
}, {
  id: 'miami',
  label: 'Miami'
}];
function SiteHeader({
  region,
  onRegion,
  onApply
}) {
  const [open, setOpen] = React.useState(false);
  return /*#__PURE__*/React.createElement("header", {
    style: {
      position: 'sticky',
      top: 0,
      zIndex: 40,
      background: 'var(--kipp-indigo)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      padding: '0 var(--space-8)',
      height: 72,
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--space-8)'
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-white-trimmed.png",
    alt: "KIPP NJ | Miami",
    style: {
      height: 34
    }
  })), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: 'flex',
      gap: 'var(--space-6)',
      marginLeft: 'var(--space-4)'
    }
  }, NAV.map(n => /*#__PURE__*/React.createElement("a", {
    key: n,
    href: "#",
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 600,
      fontSize: 13.5,
      textTransform: 'uppercase',
      letterSpacing: '.04em',
      color: 'var(--indigo-100)'
    }
  }, n))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--space-4)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setOpen(o => !o),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 7,
      cursor: 'pointer',
      background: 'rgba(255,255,255,.10)',
      border: '1px solid rgba(255,255,255,.18)',
      color: '#fff',
      borderRadius: 'var(--radius-md)',
      padding: '8px 12px',
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 12,
      textTransform: 'uppercase',
      letterSpacing: '.04em'
    }
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 24 24",
    width: "14",
    height: "14",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M12 21s-7-6.3-7-11a7 7 0 0 1 14 0c0 4.7-7 11-7 11z"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "10",
    r: "2.3"
  })), REGIONS.find(r => r.id === region)?.label, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "13",
    height: "13",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 6l4 4 4-4"
  }))), open && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 'calc(100% + 6px)',
      right: 0,
      minWidth: 160,
      background: '#fff',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-lg)',
      padding: 6,
      zIndex: 50
    }
  }, REGIONS.map(r => /*#__PURE__*/React.createElement("button", {
    key: r.id,
    onClick: () => {
      onRegion(r.id);
      setOpen(false);
    },
    style: {
      display: 'block',
      width: '100%',
      textAlign: 'left',
      cursor: 'pointer',
      background: r.id === region ? 'var(--indigo-50)' : 'transparent',
      border: 'none',
      padding: '9px 12px',
      borderRadius: 'var(--radius-sm)',
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 13,
      textTransform: 'uppercase',
      letterSpacing: '.03em',
      color: r.id === region ? 'var(--kipp-indigo)' : 'var(--text-body)'
    }
  }, r.label)))), /*#__PURE__*/React.createElement("button", {
    onClick: onApply,
    style: {
      background: 'var(--brand-accent)',
      color: 'var(--brand-on-accent)',
      border: 'none',
      borderRadius: 'var(--radius-md)',
      padding: '11px 20px',
      cursor: 'pointer',
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 13,
      textTransform: 'uppercase',
      letterSpacing: '.04em'
    }
  }, "Enroll now"))));
}
window.SiteHeader = SiteHeader;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/SiteHeader.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/StatBand.jsx
try { (() => {
const {
  StatCallout
} = window.KIPPNJMiamiDesignSystem_1916b9;
const STATS = [{
  value: '9,000+',
  label: 'Students enrolled'
}, {
  value: '20',
  label: 'Schools'
}, {
  value: '95%',
  label: 'College enrollment'
}, {
  value: '4',
  label: 'Cities'
}];
function StatBand() {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: 'var(--surface-card)',
      borderBottom: '1px solid var(--border-subtle)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      padding: 'var(--space-16) var(--space-8)',
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 'var(--space-8)'
    }
  }, STATS.map(s => /*#__PURE__*/React.createElement("div", {
    key: s.label,
    style: {
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement(StatCallout, {
    value: s.value,
    label: s.label,
    size: "lg",
    tone: "accent",
    style: {
      alignItems: 'center'
    }
  })))));
}
window.StatBand = StatBand;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/StatBand.jsx", error: String((e && e.message) || e) }); }

// ui_kits/website/ValueProps.jsx
try { (() => {
const {
  PhotoFrame
} = window;
const VALUES = [{
  t: 'Promises to children are sacred',
  d: 'We do what we say. Every child can and will learn at the highest level.'
}, {
  t: 'Outstanding TEAMmates are everything',
  d: 'Great schools are built by great people who support one another.'
}, {
  t: 'Our kids run to school',
  d: 'Joyful, rigorous classrooms where students love to learn.'
}, {
  t: 'Our kids will change the world',
  d: 'To and through college — and into lives of choice and opportunity.'
}];
function ValueProps() {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: 'var(--surface-card)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 'var(--container-max)',
      margin: '0 auto',
      padding: 'var(--space-20) var(--space-8)',
      display: 'grid',
      gridTemplateColumns: '.9fr 1.1fr',
      gap: 'var(--space-16)',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(PhotoFrame, {
    label: "Classroom",
    ratio: "4 / 5",
    tone: "orange",
    style: {
      boxShadow: 'var(--shadow-lg)'
    }
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "kf-eyebrow"
  }, "The Heartbeat"), /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 800,
      fontSize: 40,
      letterSpacing: '-.01em',
      margin: '8px 0 var(--space-8)',
      color: 'var(--text-strong)'
    }
  }, "What we believe"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gap: 'var(--space-5)'
    }
  }, VALUES.map((v, i) => /*#__PURE__*/React.createElement("div", {
    key: v.t,
    style: {
      display: 'flex',
      gap: 'var(--space-4)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 'none',
      width: 38,
      height: 38,
      borderRadius: 'var(--radius-md)',
      background: 'var(--brand-accent)',
      color: 'var(--brand-on-accent)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      fontSize: 16
    }
  }, i + 1), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: 'var(--font-brand)',
      fontWeight: 700,
      fontSize: 18,
      color: 'var(--text-strong)'
    }
  }, v.t), /*#__PURE__*/React.createElement("p", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 15,
      lineHeight: 1.5,
      color: 'var(--text-muted)',
      marginTop: 3
    }
  }, v.d))))))));
}
window.ValueProps = ValueProps;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/website/ValueProps.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Button = __ds_scope.Button;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Avatar = __ds_scope.Avatar;

__ds_ns.AvatarGroup = __ds_scope.AvatarGroup;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.StatCallout = __ds_scope.StatCallout;

__ds_ns.Tag = __ds_scope.Tag;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.SegmentedControl = __ds_scope.SegmentedControl;

__ds_ns.Tabs = __ds_scope.Tabs;

})();
