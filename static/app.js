"use strict";

// action: "register" | "pickup" | "cancel"; target: "today" | "tomorrow"
const state = { code: "", name: "", action: null, target: "today", data: null };

const $ = (id) => document.getElementById(id);

function show(stepId) {
  ["step-code", "step-action", "step-pin", "step-result"].forEach((s) => {
    $(s).classList.toggle("hidden", s !== stepId);
  });
}

function msg(el, text, ok) {
  el.innerHTML = text ? `<div class="msg ${ok ? "msg-ok" : "msg-error"}">${text}</div>` : "";
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, data };
}

// ---- Bước 1: tra cứu mã NV ----
async function lookup() {
  const code = $("code").value.trim();
  msg($("msg-code"), "", false);
  if (!code) { msg($("msg-code"), "Vui lòng nhập mã nhân viên.", false); return; }

  $("btn-lookup").disabled = true;
  const { data } = await postJSON("/api/lookup", { code });
  $("btn-lookup").disabled = false;

  if (!data.ok) { msg($("msg-code"), data.error || "Có lỗi xảy ra.", false); return; }

  state.code = code;
  state.name = data.name;
  state.data = data;
  state.target = "today";
  $("emp-name").textContent = data.name;
  $("emp-dept").textContent = data.department || "";

  // Nhãn ngày trên bộ chọn
  $("seg-today").innerHTML = `Hôm nay<small>${data.today.date}</small>`;
  $("seg-tomorrow").innerHTML = `Ngày mai<small>${data.tomorrow.date}</small>`;
  // Ẩn lựa chọn ngày mai nếu HC tắt tính năng
  $("seg-tomorrow").classList.toggle("hidden", !data.allow_next_day);
  setActiveSeg("today");

  renderDay();
  show("step-action");
}

function setActiveSeg(target) {
  state.target = target;
  $("seg-today").classList.toggle("active", target === "today");
  $("seg-tomorrow").classList.toggle("active", target === "tomorrow");
}

// Hiển thị trạng thái + nút phù hợp cho ngày đang chọn
function renderDay() {
  const day = state.data[state.target];
  const isToday = state.target === "today";

  const tags = [];
  tags.push(day.registered
    ? `<span class="tag tag-ok">Đã đăng ký (${day.date})</span>`
    : `<span class="tag tag-no">Chưa đăng ký (${day.date})</span>`);
  if (day.picked_up) tags.push(`<span class="tag tag-ok">Đã nhận cơm</span>`);
  $("status-row").innerHTML = tags.join("");

  // Đăng ký: hiện khi chưa đăng ký cho ngày này
  $("btn-do-register").classList.toggle("hidden", day.registered);
  // Hủy: hiện khi đã đăng ký mà chưa nhận
  $("btn-do-cancel").classList.toggle("hidden", !(day.registered && !day.picked_up));
  // Nhận cơm: chỉ áp dụng cho hôm nay, khi đã đăng ký và chưa nhận
  $("btn-do-pickup").classList.toggle("hidden", !(isToday && day.registered && !day.picked_up));
}

// ---- Bước 2 -> 3 ----
function goPin(action) {
  state.action = action;
  $("pin").value = "";
  msg($("msg-pin"), "", false);
  const dayTxt = state.target === "today"
    ? `hôm nay (${state.data.today.date})`
    : `ngày mai (${state.data.tomorrow.date})`;
  if (action === "register") {
    $("pin-title").textContent = "Đăng ký đặt cơm";
    $("pin-sub").textContent = `${state.name} — nhập PIN để đăng ký cho ${dayTxt}.`;
  } else if (action === "pickup") {
    $("pin-title").textContent = "Xác nhận nhận cơm";
    $("pin-sub").textContent = `${state.name} — nhập PIN để xác nhận đã lấy cơm.`;
  } else {
    $("pin-title").textContent = "Hủy đăng ký";
    $("pin-sub").textContent = `${state.name} — nhập PIN để hủy suất cơm ${dayTxt}.`;
  }
  show("step-pin");
  setTimeout(() => $("pin").focus(), 100);
}

// ---- Bước 3: xác nhận PIN ----
async function confirmAction() {
  const pin = $("pin").value.trim();
  msg($("msg-pin"), "", false);
  if (!pin) { msg($("msg-pin"), "Vui lòng nhập mã PIN.", false); return; }

  const urls = { register: "/api/register", pickup: "/api/pickup", cancel: "/api/cancel" };
  const url = urls[state.action];
  const body = { code: state.code, pin };
  if (state.action !== "pickup") body.target = state.target; // nhận cơm luôn là hôm nay

  $("btn-confirm").disabled = true;
  const { data } = await postJSON(url, body);
  $("btn-confirm").disabled = false;

  if (!data.ok) { msg($("msg-pin"), data.error || "Có lỗi xảy ra.", false); return; }

  const icons = { register: "🍱", pickup: "✅", cancel: "🗑" };
  $("result-icon").textContent = icons[state.action] || "✅";
  $("result-title").textContent = data.message;
  $("result-time").textContent = data.time ? `Thời gian: ${data.time}` : "";
  show("step-result");
}

function reset() {
  state.code = ""; state.name = ""; state.action = null; state.target = "today"; state.data = null;
  $("code").value = ""; $("pin").value = "";
  msg($("msg-code"), "", false);
  show("step-code");
  setTimeout(() => $("code").focus(), 100);
}

// ---- Sự kiện ----
$("btn-lookup").addEventListener("click", lookup);
$("code").addEventListener("keydown", (e) => { if (e.key === "Enter") lookup(); });

$("seg-today").addEventListener("click", () => { setActiveSeg("today"); renderDay(); });
$("seg-tomorrow").addEventListener("click", () => { setActiveSeg("tomorrow"); renderDay(); });

$("btn-do-register").addEventListener("click", () => goPin("register"));
$("btn-do-pickup").addEventListener("click", () => goPin("pickup"));
$("btn-do-cancel").addEventListener("click", () => goPin("cancel"));
$("btn-back-1").addEventListener("click", reset);

$("btn-confirm").addEventListener("click", confirmAction);
$("pin").addEventListener("keydown", (e) => { if (e.key === "Enter") confirmAction(); });
$("btn-back-2").addEventListener("click", () => show("step-action"));

$("btn-done").addEventListener("click", reset);
