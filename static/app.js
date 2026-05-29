"use strict";

const state = { code: "", name: "", action: null }; // action: "register" | "pickup" | "cancel"

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
  $("emp-name").textContent = data.name;
  $("emp-dept").textContent = data.department || "";

  // Trạng thái hôm nay
  const tags = [];
  tags.push(data.registered
    ? `<span class="tag tag-ok">Đã đăng ký hôm nay</span>`
    : `<span class="tag tag-no">Chưa đăng ký</span>`);
  if (data.picked_up) tags.push(`<span class="tag tag-ok">Đã nhận cơm</span>`);
  $("status-row").innerHTML = tags.join("");

  // Chỉ cho hủy khi đã đăng ký mà chưa nhận cơm
  $("btn-do-cancel").classList.toggle("hidden", !(data.registered && !data.picked_up));

  show("step-action");
}

// ---- Bước 2 -> 3 ----
function goPin(action) {
  state.action = action;
  $("pin").value = "";
  msg($("msg-pin"), "", false);
  if (action === "register") {
    $("pin-title").textContent = "Đăng ký đặt cơm";
    $("pin-sub").textContent = `${state.name} — nhập PIN để xác nhận đăng ký.`;
  } else if (action === "pickup") {
    $("pin-title").textContent = "Xác nhận nhận cơm";
    $("pin-sub").textContent = `${state.name} — nhập PIN để xác nhận đã lấy cơm.`;
  } else {
    $("pin-title").textContent = "Hủy đăng ký";
    $("pin-sub").textContent = `${state.name} — nhập PIN để xác nhận hủy suất cơm hôm nay.`;
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
  $("btn-confirm").disabled = true;
  const { data } = await postJSON(url, { code: state.code, pin });
  $("btn-confirm").disabled = false;

  if (!data.ok) {
    msg($("msg-pin"), data.error || "Có lỗi xảy ra.", false);
    return;
  }

  const icons = { register: "🍱", pickup: "✅", cancel: "🗑" };
  $("result-icon").textContent = icons[state.action] || "✅";
  $("result-title").textContent = data.message;
  $("result-time").textContent = data.time ? `Thời gian: ${data.time}` : "";
  show("step-result");
}

function reset() {
  state.code = ""; state.name = ""; state.action = null;
  $("code").value = ""; $("pin").value = "";
  msg($("msg-code"), "", false);
  show("step-code");
  setTimeout(() => $("code").focus(), 100);
}

// ---- Sự kiện ----
$("btn-lookup").addEventListener("click", lookup);
$("code").addEventListener("keydown", (e) => { if (e.key === "Enter") lookup(); });

$("btn-do-register").addEventListener("click", () => goPin("register"));
$("btn-do-pickup").addEventListener("click", () => goPin("pickup"));
$("btn-do-cancel").addEventListener("click", () => goPin("cancel"));
$("btn-back-1").addEventListener("click", reset);

$("btn-confirm").addEventListener("click", confirmAction);
$("pin").addEventListener("keydown", (e) => { if (e.key === "Enter") confirmAction(); });
$("btn-back-2").addEventListener("click", () => show("step-action"));

$("btn-done").addEventListener("click", reset);
