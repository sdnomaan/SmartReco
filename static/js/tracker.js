(function () {
  const QUEUE_LIMIT = 20;
  const FLUSH_INTERVAL_MS = 5000;
  const STORAGE_KEY = "smartreco_session_id";

  function getSessionId() {
    let sessionId = sessionStorage.getItem(STORAGE_KEY);
    if (!sessionId) {
      sessionId = (crypto && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);
      sessionStorage.setItem(STORAGE_KEY, sessionId);
    }
    return sessionId;
  }

  function nowIso() {
    return new Date().toISOString();
  }

  class SmartRecoTracker {
    constructor() {
      this.queue = [];
      this.sessionId = getSessionId();
      this.flushTimer = null;
      this.productViewStartedAt = null;
      this.bindLifecycle();
      this.bindClicks();
      this.bootstrapPageEvents();
      this.scheduleFlush();
    }

    enqueue(event) {
      this.queue.push(event);
      if (this.queue.length >= QUEUE_LIMIT) {
        this.flush(false);
      }
    }

    flush(useBeacon) {
      if (!this.queue.length) {
        return;
      }
      const events = this.queue.splice(0, this.queue.length);
      const payload = JSON.stringify({ events });
      const url = "/api/events/batch";

      if (useBeacon && navigator.sendBeacon) {
        const success = navigator.sendBeacon(url, new Blob([payload], { type: "application/json" }));
        if (success) {
          return;
        }
      }

      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: Boolean(useBeacon),
        credentials: "same-origin",
      }).catch(() => {
        // Re-queueing is intentionally omitted to keep this tracker lightweight.
      });
    }

    scheduleFlush() {
      if (this.flushTimer) {
        clearTimeout(this.flushTimer);
      }
      this.flushTimer = setTimeout(() => {
        this.flush(false);
        this.scheduleFlush();
      }, FLUSH_INTERVAL_MS);
    }

    bindLifecycle() {
      window.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") {
          this.captureDwell();
          this.flush(true);
        }
      });

      window.addEventListener("pagehide", () => {
        this.captureDwell();
        this.flush(true);
      });
    }

    bindClicks() {
      document.addEventListener("click", (event) => {
        const target = event.target.closest("[data-smartreco-click]");
        if (!target) {
          return;
        }
        this.trackClick(target.dataset.smartrecoClick || target.tagName.toLowerCase(), {
          element_id: target.id || null,
          text: (target.textContent || "").trim().slice(0, 120),
        });
      });
    }

    bootstrapPageEvents() {
      const body = document.body;
      const pageType = body.dataset.smartrecoPageType || "page_view";
      const sessionId = body.dataset.smartrecoSessionId || this.sessionId;
      this.sessionId = sessionId;

      this.trackPageView({ page_type: pageType, path: window.location.pathname });

      if (body.dataset.smartrecoCategory) {
        this.trackCategoryView(body.dataset.smartrecoCategory);
      }

      if (body.dataset.smartrecoProductId) {
        this.productViewStartedAt = Date.now();
        this.trackProductView(body.dataset.smartrecoProductId, {
          category: body.dataset.smartrecoCategory || null,
        });
      }
    }

    buildEvent(eventType, payload) {
      return {
        session_id: this.sessionId,
        event_type: eventType,
        metadata: {
          ...payload,
          client_timestamp: nowIso(),
        },
        ...payload,
      };
    }

    trackPageView(payload = {}) {
      this.enqueue(this.buildEvent("PAGE_VIEW", payload));
    }

    trackProductView(productId, payload = {}) {
      this.enqueue({
        ...this.buildEvent("PRODUCT_VIEW", payload),
        product_id: Number(productId),
      });
    }

    trackSearch(query) {
      if (!query) {
        return;
      }
      this.enqueue(this.buildEvent("SEARCH", { search_query: query }));
    }

    trackCategoryView(category) {
      if (!category) {
        return;
      }
      this.enqueue(this.buildEvent("CATEGORY_VIEW", { category }));
    }

    trackClick(clickType, payload = {}) {
      this.enqueue(this.buildEvent("CLICK", { click_type: clickType, ...payload }));
    }

    captureDwell() {
      const productId = document.body.dataset.smartrecoProductId;
      if (!productId || this.productViewStartedAt === null) {
        return;
      }
      const durationMs = Math.max(0, Date.now() - this.productViewStartedAt);
      this.enqueue(this.buildEvent("DWELL", {
        product_id: Number(productId),
        duration_ms: durationMs,
      }));
      this.productViewStartedAt = null;
    }
  }

  window.SmartRecoTracker = new SmartRecoTracker();
})();