// Let's Meet Morocco v3 — JS Principal

// Auto-scroll chat
function scrollChat() {
  const b = document.getElementById("chat-box");
  if (b) b.scrollTop = b.scrollHeight;
}
document.addEventListener("DOMContentLoaded", scrollChat);

// Fermer alertes après 4s
document.addEventListener("DOMContentLoaded", function () {
  setTimeout(function () {
    document.querySelectorAll(".alert").forEach(function (el) {
      el.style.transition = "opacity .5s";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 500);
    });
  }, 4000);
});

// Confirmation
function confirmer(msg) { return confirm(msg || "Êtes-vous sûr ?"); }

// Max 5 centres d'intérêt
document.addEventListener("DOMContentLoaded", function () {
  const boxes = document.querySelectorAll(".centre-check");
  if (!boxes.length) return;
  boxes.forEach(function (cb) {
    cb.addEventListener("change", function () {
      const el = document.getElementById("centres-count");
      if (el) {
        const n = document.querySelectorAll(".centre-check:checked").length;
        if (n < 5) {
          el.textContent = n + " sélectionnés — encore " + (5 - n) + " minimum requis";
          el.style.color = "#E8541A";
        } else {
          el.textContent = "✅ " + n + " sélectionnés";
          el.style.color = "#00B4D8";
        }
      }
    });
  });
});

// Aperçu photo
function previewPhoto(input) {
  if (input.files && input.files[0]) {
    const r = new FileReader();
    r.onload = function (e) {
      const av = document.getElementById("avatar-preview");
      if (!av) return;
      if (av.tagName === "DIV") {
        av.innerHTML = '<img src="' + e.target.result + '" style="width:100%;height:100%;object-fit:cover;border-radius:50%">';
      } else {
        av.src = e.target.result;
      }
    };
    r.readAsDataURL(input.files[0]);
  }
}

// Chat auto-refresh toutes les 5s
function startChatRefresh(actId, currentUserId) {
  let lastMsgId = 0;
  let isFirstLoad = true;

  function buildBubble(m, isMoi) {
    const statusDot = m.en_ligne
      ? '<span style="width:8px;height:8px;border-radius:50%;background:#2DB54C;display:inline-block;margin-right:4px;vertical-align:middle"></span>'
      : '';
    const div = document.createElement("div");
    div.className = "chat-msg" + (isMoi ? " moi" : "");
    div.dataset.msgId = m.id;
    div.innerHTML =
      '<div class="chat-bubble">' +
        '<div class="sender">' + statusDot + m.prenom + '</div>' +
        '<div class="text">' + m.contenu + '</div>' +
        '<div class="time">' + m.heure + (isMoi ? ' <span style="color:#4FC3F7">✓✓</span>' : '') + '</div>' +
      '</div>';
    return div;
  }

  function refresh() {
    fetch("/api/messages/" + actId)
      .then(function(r) { return r.json(); })
      .then(function(msgs) {
        const box = document.getElementById("chat-box");
        if (!box) return;

        if (msgs.length === 0 && isFirstLoad) {
          box.innerHTML = '<div style="text-align:center;padding:30px;color:#aaa;font-size:14px">💬 Aucun message. Lance la conversation !</div>';
          isFirstLoad = false;
          return;
        }

        // Ajouter seulement les nouveaux messages (évite le rebuild complet)
        const newMsgs = msgs.filter(function(m) { return m.id > lastMsgId; });
        if (newMsgs.length === 0) return;

        // Premier chargement : vider et tout afficher
        if (isFirstLoad) {
          box.innerHTML = "";
          msgs.forEach(function(m) {
            box.appendChild(buildBubble(m, m.user_id == currentUserId));
          });
          isFirstLoad = false;
        } else {
          // Nouveaux messages seulement
          newMsgs.forEach(function(m) {
            box.appendChild(buildBubble(m, m.user_id == currentUserId));
          });
        }

        if (msgs.length > 0) {
          lastMsgId = msgs[msgs.length - 1].id;
        }
        box.scrollTop = box.scrollHeight;
      })
      .catch(function() {}); // Silencieux si erreur réseau
  }

  // Premier appel immédiat, puis toutes les 3 secondes
  refresh();
  setInterval(refresh, 3000);
}

// Badge notifications
function refreshNotifCount() {
  fetch("/api/notifs_count")
    .then(function (r) { return r.json(); })
    .then(function (d) {
      const badge = document.getElementById("notif-badge");
      if (!badge) return;
      if (d.count > 0) { badge.textContent = d.count; badge.style.display = "block"; }
      else { badge.style.display = "none"; }
    });
}
document.addEventListener("DOMContentLoaded", function () {
  refreshNotifCount();
  setInterval(refreshNotifCount, 15000);
});

// Vérif âge à l'inscription
function checkAge(inp) {
  const h = document.getElementById("age-hint");
  if (!h) return;
  const dn = new Date(inp.value);
  const age = Math.floor((new Date() - dn) / 1000 / 60 / 60 / 24 / 365);
  if (isNaN(age)) { h.textContent = ""; return; }
  if (age < 18) { h.textContent = "❌ Vous devez avoir 18 ans minimum"; h.style.color = "#E8541A"; }
  else { h.textContent = "✅ " + age + " ans"; h.style.color = "#00B4D8"; }
}

// Vérif mot de passe
function checkMdp(inp) {
  const h = document.getElementById("mdp-hint");
  if (!h) return;
  const len = inp.value.length;
  if (len === 0) { h.textContent = ""; return; }
  if (len < 6) { h.textContent = "❌ Trop court (" + len + "/6)"; h.style.color = "#E8541A"; }
  else { h.textContent = "✅ Mot de passe valide"; h.style.color = "#00B4D8"; }
}

// Helpers initiales pour avatars
function updateInitials() {
  const p = document.getElementById("inp-prenom");
  const n = document.getElementById("inp-nom");
  const av = document.getElementById("avatar-preview");
  if (!p || !n || !av) return;
  if (!av.querySelector("img")) {
    av.textContent = (p.value[0] || "") + (n.value[0] || "") || "📷";
  }
}

// Tab switcher pour edit_profile
function showTab(t) {
  ["profil","mdp"].forEach(function(name) {
    const sec = document.getElementById("section-" + name);
    const tab = document.getElementById("tab-" + name);
    if (!sec || !tab) return;
    sec.style.display = t === name ? "block" : "none";
    tab.className = "btn " + (t === name ? "btn-green" : "btn-outline");
  });
}

// ══ NOUVELLES FONCTIONS v12 ══════════════════════════

// Countdown timer sur toutes les cards
function initCountdowns() {
  document.querySelectorAll('.countdown').forEach(function(el) {
    const dateStr = el.dataset.date || el.textContent;
    const parts = dateStr.trim().split(' ');
    const dp = parts[0].split('/');
    const tp = (parts[1]||'00:00').split(':');
    let target;
    if(dp.length===3) {
      target = new Date(dp[2], dp[1]-1, dp[0], tp[0]||0, tp[1]||0);
    } else {
      target = new Date(parts[0]+'T'+(parts[1]||'00:00'));
    }
    function update() {
      const diff = target - new Date();
      if(isNaN(diff)||diff<=0) { return; }
      const days = Math.floor(diff/86400000);
      const hours = Math.floor((diff%86400000)/3600000);
      const mins = Math.floor((diff%3600000)/60000);
      if(days>7) return;
      if(days>0) el.textContent = '⏰ Dans '+days+'j '+hours+'h';
      else if(hours>0) el.textContent = '⏰ Dans '+hours+'h '+mins+'min';
      else el.textContent = '🔴 Dans '+mins+'min';
    }
    update();
    setInterval(update, 60000);
  });
}
document.addEventListener('DOMContentLoaded', initCountdowns);

// Toast notifications globales
function showToast(msg, type) {
  let c = document.getElementById('toast-container');
  if(!c) {
    c = document.createElement('div');
    c.className = 'toast-container';
    c.id = 'toast-container';
    document.body.appendChild(c);
  }
  const t = document.createElement('div');
  t.className = 'toast' + (type ? ' t-'+type : '');
  t.innerHTML = msg;
  c.appendChild(t);
  setTimeout(function() { t.remove(); }, 4200);
}

// Vibration légère sur les boutons (mobile)
document.addEventListener('click', function(e) {
  if(e.target.classList.contains('btn') || e.target.closest('.btn')) {
    if(navigator.vibrate) navigator.vibrate(10);
  }
});
