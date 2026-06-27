(() => {
  const TOTAL_STEPS = 7;

  function initDateSelects() {
    const daySelect = document.getElementById("renewalDay");
    const yearSelect = document.getElementById("renewalYear");
    if (!daySelect || !yearSelect) return;

    // Clear and refill
    daySelect.innerHTML = '<option value="">Day</option>';
    yearSelect.innerHTML = '<option value="">Year</option>';

    for (let d = 1; d <= 31; d++) {
      const val = String(d).padStart(2, "0");
      daySelect.add(new Option(val, val));
    }

    const currentYear = new Date().getFullYear();
    for (let y = currentYear; y <= currentYear + 5; y++) {
      yearSelect.add(new Option(String(y), String(y)));
    }
  }

  function syncRenewalDate() {
    const month = document.getElementById("renewalMonth")?.value;
    const day = document.getElementById("renewalDay")?.value;
    const year = document.getElementById("renewalYear")?.value;
    const hidden = document.getElementById("subRenewal");
    if (hidden && month && day && year) {
      hidden.value = `${year}-${month}-${day}`;
    } else if (hidden) {
      hidden.value = "";
    }
  }

  function initWizard() {
    const form = document.getElementById("addSubForm");
    if (!form) return;

    initDateSelects();
    ["renewalMonth", "renewalDay", "renewalYear"].forEach((id) => {
      document.getElementById(id)?.addEventListener("change", syncRenewalDate);
    });

    let step = 1;
    const steps = form.querySelectorAll(".wizard-step");
    const backBtn = document.getElementById("wizardBack");
    const nextBtn = document.getElementById("wizardNext");
    const submitBtn = document.getElementById("wizardSubmit");
    const progress = document.getElementById("wizardProgress");
    const modal = document.getElementById("addSubModal");

    function showStep(n) {
      step = n;
      steps.forEach((el) => el.classList.toggle("active", Number(el.dataset.step) === step));
      backBtn.style.visibility = step > 1 ? "visible" : "hidden";
      nextBtn.style.display = step < TOTAL_STEPS ? "inline-block" : "none";
      submitBtn.style.display = step === TOTAL_STEPS ? "inline-block" : "none";
      progress.style.width = `${(step / TOTAL_STEPS) * 100}%`;
      if (step === TOTAL_STEPS) fillReview();
    }

    function currentStepValid() {
      const active = form.querySelector(`.wizard-step[data-step="${step}"]`);
      if (!active) return false;

      // Step 5 = renewal date
      if (step === 5) {
        syncRenewalDate();
        const month = document.getElementById("renewalMonth");
        const day = document.getElementById("renewalDay");
        const year = document.getElementById("renewalYear");
        if (!month?.value || !day?.value || !year?.value) {
          month?.reportValidity();
          return false;
        }
        return true;
      }

      const inputs = active.querySelectorAll("input[required], select[required]");
      for (const input of inputs) {
        if (input.type === "radio") {
          if (!form.querySelector(`input[name="${input.name}"]:checked`)) return false;
        } else if (!input.value.trim()) {
          input.reportValidity();
          return false;
        }
      }
      return true;
    }

    function fillReview() {
      syncRenewalDate();
      const name = document.getElementById("subName").value;
      const cost = document.getElementById("subCost").value;
      const currency = document.getElementById("subCurrency")?.value || "USD";
      const category = document.getElementById("subCategory")?.value || "Other";
      const cycle = form.querySelector('input[name="cycle"]:checked')?.value || "-";
      const renewal = document.getElementById("subRenewal").value;
      const method = document.getElementById("subMethod").value;
      document.getElementById("reviewBox").innerHTML = `
        <p><strong>Service:</strong> ${name}</p>
        <p><strong>Cost:</strong> ${currency} ${parseFloat(cost).toFixed(2)} / ${cycle.toLowerCase()}</p>
        <p><strong>Category:</strong> ${category}</p>
        <p><strong>Renews:</strong> ${renewal}</p>
        <p><strong>Payment:</strong> ${method}</p>
      `;
    }

    nextBtn.addEventListener("click", () => {
      if (!currentStepValid()) return;
      if (step < TOTAL_STEPS) showStep(step + 1);
    });

    backBtn.addEventListener("click", () => {
      if (step > 1) showStep(step - 1);
    });

    form.addEventListener("submit", (e) => {
      syncRenewalDate();
      if (!document.getElementById("subRenewal").value) {
        e.preventDefault();
        showStep(5);
      }
    });

    modal?.addEventListener("hidden.bs.modal", () => {
      form.reset();
      initDateSelects();
      showStep(1);
    });

    showStep(1);
  }

  function initAiModal() {
    const fab = document.getElementById("aiFabBtn");
    const form = document.getElementById("aiForm");
    const modalEl = document.getElementById("aiModal");
    if (!fab || !form || !modalEl) return;

    const modal = new bootstrap.Modal(modalEl);
    const responseEl = document.getElementById("aiResponse");
    const loadingEl = document.getElementById("aiLoading");
    const submitBtn = document.getElementById("aiSubmitBtn");

    fab.addEventListener("click", () => {
      responseEl.innerHTML = "";
      modal.show();
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.getElementById("aiServiceInput");
      const service = input.value.trim();
      if (!service) return;

      loadingEl.style.display = "block";
      responseEl.innerHTML = "";
      submitBtn.disabled = true;

      try {
        const body = new FormData();
        body.append("service_name", service);
        const res = await fetch("/ai/ask", { method: "POST", body });
        const data = await res.json();
        responseEl.innerHTML = data.html || "<p>Something went wrong.</p>";
      } catch {
        responseEl.innerHTML = "<p class='text-danger'>Could not reach the AI assistant.</p>";
      } finally {
        loadingEl.style.display = "none";
        submitBtn.disabled = false;
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initWizard();
    initAiModal();
  });
})();
