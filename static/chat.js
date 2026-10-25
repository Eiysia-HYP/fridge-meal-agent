const state = {
  sessionId: localStorage.getItem("fridge_session") || null,
};

const $ = (id) => document.getElementById(id);

function appendMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  $("messages").appendChild(wrap);
  $("messages").scrollTop = $("messages").scrollHeight;
  return bubble;
}

function card(title, rows) {
  const box = document.createElement("div");
  box.className = "trace-card";
  const h = document.createElement("h4");
  h.textContent = title;
  box.appendChild(h);
  rows.forEach((row) => {
    const p = document.createElement("p");
    p.textContent = row;
    box.appendChild(p);
  });
  return box;
}

function renderTrace(trace) {
  if (!trace || !trace.length) return;
  const wrap = document.createElement("div");
  wrap.className = "msg assistant";
  const holder = document.createElement("div");
  holder.className = "bubble trace";

  trace.forEach((step) => {
    const r = step.result || {};
    if (step.name === "get_inventory" && Array.isArray(r.items)) {
      holder.appendChild(
        card(
          "库存查询结果",
          r.items.length
            ? r.items.map((i) => `${i.name}：${i.quantity}${i.unit}`)
            : ["库存中没有匹配的食材"]
        )
      );
    } else if (step.name === "search_recipes" && Array.isArray(r.recipes)) {
      holder.appendChild(
        card(
          "菜谱搜索结果",
          r.recipes.length
            ? r.recipes.map((x) => `${x.name}（${x.area || "未知地区"}）`)
            : [r.warning || "没有找到菜谱"]
        )
      );
    } else if ((step.name === "generate_meal_plan" || step.name === "modify_meal_plan") && Array.isArray(r.slots)) {
      const rows = r.slots.map((s) => {
        const miss = s.missing.length ? `缺：${s.missing.map((m) => m.name).join("、")}` : "库存可覆盖";
        return `${s.slot}：${s.recipe.name} · ${miss}`;
      });
      holder.appendChild(card("当前计划", rows.length ? rows : [r.error || "计划为空"]));
    } else if (step.name === "generate_shopping_list" && Array.isArray(r.items)) {
      holder.appendChild(
        card(
          "购物清单",
          r.items.length ? r.items.map((i) => `${i.name} ${i.measure || ""}`) : ["无需采购"]
        )
      );
    } else if (r.error) {
      holder.appendChild(card(`工具 ${step.name} 失败`, [r.error]));
    }
  });

  wrap.appendChild(holder);
  $("messages").appendChild(wrap);
  $("messages").scrollTop = $("messages").scrollHeight;
}

function speak(text) {
  if (!$("speakToggle").checked || !window.speechSynthesis) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

async function send() {
  const input = $("message");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  appendMessage("user", text);

  const placeholder = appendMessage("assistant", "正在处理…");
  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: state.sessionId, message: text }),
    });
    const data = await resp.json();
    state.sessionId = data.sessionId;
    localStorage.setItem("fridge_session", state.sessionId);

    placeholder.textContent = data.reply || "（无回复）";
    renderTrace(data.toolTrace);
    speak(data.reply || "");
  } catch (err) {
    placeholder.textContent = "请求失败：" + err.message;
  }
}

function startVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    alert("当前浏览器不支持语音输入，请使用 Chrome 或 Edge。");
    return;
  }
  const recognition = new SR();
  recognition.lang = "zh-CN";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onresult = (event) => {
    $("message").value = event.results[0][0].transcript;
  };
  recognition.onerror = (event) => {
    alert("语音识别失败：" + event.error);
  };
  recognition.start();
}

$("sendBtn").addEventListener("click", send);
$("voiceBtn").addEventListener("click", startVoice);
$("message").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
