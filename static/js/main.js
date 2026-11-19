/* ============================================================
   Waste Wise Bengaluru — Main JavaScript
   ============================================================ */

(function () {
  "use strict";

  /* ---- Sidebar toggle (mobile) ---- */
  function initSidebar() {
    var toggleBtn = document.getElementById("sidebarToggle");
    var sidebar = document.getElementById("appSidebar");
    if (!toggleBtn || !sidebar) return;

    var overlay = document.createElement("div");
    overlay.className = "sidebar-overlay";
    overlay.style.display = "none";
    document.body.appendChild(overlay);

    toggleBtn.addEventListener("click", function () {
      var isOpen = sidebar.classList.toggle("open");
      overlay.style.display = isOpen ? "block" : "none";
    });

    overlay.addEventListener("click", function () {
      sidebar.classList.remove("open");
      overlay.style.display = "none";
    });
  }

  /* ---- Auto-dismiss flash messages ---- */
  function initAlerts() {
    var alerts = document.querySelectorAll(".alert[data-autohide]");
    alerts.forEach(function (el) {
      var delay = parseInt(el.dataset.autohide, 10) || 4000;
      setTimeout(function () {
        el.style.transition = "opacity .4s";
        el.style.opacity = "0";
        setTimeout(function () { el.remove(); }, 420);
      }, delay);
    });

    // Manual dismiss buttons
    document.querySelectorAll(".alert-dismiss").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var alert = btn.closest(".alert");
        if (alert) {
          alert.style.transition = "opacity .2s";
          alert.style.opacity = "0";
          setTimeout(function () { alert.remove(); }, 220);
        }
      });
    });
  }

  /* ---- Confirm dialogs for status changes / destructive actions ---- */
  function initConfirm() {
    document.querySelectorAll("[data-confirm]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        var msg = el.dataset.confirm || "Are you sure?";
        if (!window.confirm(msg)) {
          e.preventDefault();
          e.stopPropagation();
        }
      });
    });
  }

  /* ---- Expandable table rows ---- */
  function initExpandable() {
    document.querySelectorAll(".expandable-row").forEach(function (row) {
      row.addEventListener("click", function () {
        var nextRow = row.nextElementSibling;
        if (nextRow && nextRow.classList.contains("detail-row")) {
          nextRow.classList.toggle("open");
        }
      });
    });
  }

  /* ---- Notification count refresh (every 30s) ---- */
  function initNotifRefresh() {
    var badge = document.getElementById("notifBadge");
    if (!badge) return;

    function refresh() {
      fetch("/api/notifications/unread-count", { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (data && typeof data.count === "number") {
            badge.textContent = data.count > 99 ? "99+" : data.count;
            badge.style.display = data.count > 0 ? "flex" : "none";
          }
        })
        .catch(function () { /* silent fail */ });
    }

    setInterval(refresh, 30000);
  }

  /* ---- Simple form validation ---- */
  function initFormValidation() {
    var forms = document.querySelectorAll("form[data-validate]");
    forms.forEach(function (form) {
      form.addEventListener("submit", function (e) {
        var valid = true;
        form.querySelectorAll("[required]").forEach(function (field) {
          if (!field.value.trim()) {
            field.classList.add("invalid");
            valid = false;
          } else {
            field.classList.remove("invalid");
          }
        });
        if (!valid) {
          e.preventDefault();
          var firstInvalid = form.querySelector(".invalid");
          if (firstInvalid) firstInvalid.focus();
        }
      });

      // Live remove invalid class when user types
      form.querySelectorAll("[required]").forEach(function (field) {
        field.addEventListener("input", function () {
          if (field.value.trim()) field.classList.remove("invalid");
        });
      });

      // Password match check
      var pwd1 = form.querySelector("#password");
      var pwd2 = form.querySelector("#confirm_password");
      if (pwd1 && pwd2) {
        form.addEventListener("submit", function (e) {
          if (pwd1.value && pwd2.value && pwd1.value !== pwd2.value) {
            pwd2.classList.add("invalid");
            var err = pwd2.parentElement.querySelector(".form-error");
            if (err) { err.style.display = "block"; err.textContent = "Passwords do not match."; }
            e.preventDefault();
          }
        });
      }
    });
  }

  /* ---- File upload label update ---- */
  function initFileUpload() {
    document.querySelectorAll(".file-upload-area input[type='file']").forEach(function (input) {
      input.addEventListener("change", function () {
        var label = input.closest(".file-upload-area");
        if (!label) return;
        var text = label.querySelector(".upload-text");
        if (text) {
          text.textContent = input.files.length
            ? input.files[0].name
            : "Click or drag a photo here (optional)";
        }
      });
    });
  }

  /* ---- Status-change form confirmation ---- */
  function initStatusForms() {
    document.querySelectorAll("form[data-status-form]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        var select = form.querySelector("select[name='new_status']");
        var newVal = select ? select.value : "";
        if (newVal && !window.confirm("Update status to: " + newVal + "?")) {
          e.preventDefault();
        }
      });
    });
  }

  /* ---- SVG bar chart helper (used by inline templates) ---- */
  window.WWB = window.WWB || {};

  window.WWB.renderBarChart = function (containerId, labels, values, color) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var W = container.clientWidth || 400;
    var H = 160;
    var padL = 40, padR = 10, padT = 10, padB = 30;
    var chartW = W - padL - padR;
    var chartH = H - padT - padB;
    var max = Math.max.apply(null, values) || 1;
    var barW = Math.floor(chartW / labels.length * 0.6);
    var gap = Math.floor(chartW / labels.length);
    color = color || "#2d6a4f";

    var bars = "";
    labels.forEach(function (lbl, i) {
      var bh = Math.round((values[i] / max) * chartH);
      var x = padL + i * gap + (gap - barW) / 2;
      var y = padT + chartH - bh;
      bars += '<rect x="' + x + '" y="' + y + '" width="' + barW + '" height="' + bh + '" fill="' + color + '" rx="3"/>';
      bars += '<text x="' + (x + barW / 2) + '" y="' + (H - 5) + '" text-anchor="middle" font-size="9" fill="#6b7280">' + lbl + "</text>";
      bars += '<text x="' + (x + barW / 2) + '" y="' + (y - 3) + '" text-anchor="middle" font-size="9" fill="' + color + '">' + values[i] + "</text>";
    });

    container.innerHTML = '<svg width="100%" height="' + H + '" viewBox="0 0 ' + W + " " + H + '">' + bars + '</svg>';
  };

  window.WWB.renderLineChart = function (containerId, labels, values, color) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var W = container.clientWidth || 400;
    var H = 140;
    var padL = 36, padR = 10, padT = 12, padB = 28;
    var chartW = W - padL - padR;
    var chartH = H - padT - padB;
    var max = Math.max.apply(null, values) || 1;
    color = color || "#2d6a4f";
    var n = labels.length;

    var pts = labels.map(function (_, i) {
      var x = padL + (i / (n - 1 || 1)) * chartW;
      var y = padT + chartH - (values[i] / max) * chartH;
      return x + "," + y;
    }).join(" ");

    var dots = labels.map(function (lbl, i) {
      var x = padL + (i / (n - 1 || 1)) * chartW;
      var y = padT + chartH - (values[i] / max) * chartH;
      return '<circle cx="' + x + '" cy="' + y + '" r="3" fill="' + color + '"/>'
        + '<text x="' + x + '" y="' + (H - 4) + '" text-anchor="middle" font-size="9" fill="#6b7280">' + lbl + "</text>";
    }).join("");

    container.innerHTML = '<svg width="100%" height="' + H + '" viewBox="0 0 ' + W + " " + H + '">'
      + '<polyline points="' + pts + '" fill="none" stroke="' + color + '" stroke-width="2.5" stroke-linejoin="round"/>'
      + dots
      + '</svg>';
  };

  /* ---- Notification button click ---- */
  function initNotifBtn() {
    var btn = document.getElementById("notifBtn");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var url = btn.getAttribute("data-url");
      if (url && url !== "#") window.location.href = url;
    });
  }

  /* ---- Bootstrap ---- */
  document.addEventListener("DOMContentLoaded", function () {
    initSidebar();
    initAlerts();
    initConfirm();
    initExpandable();
    initNotifRefresh();
    initFormValidation();
    initFileUpload();
    initStatusForms();
    initNotifBtn();
  });
})();
