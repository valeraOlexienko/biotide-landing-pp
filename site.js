(function () {
    "use strict";

    // ------------------------------------------------------------------ config
    // Everything site-specific lives in this block. The scaffold fills the
    // tokens; edit by hand afterwards and bump `site.js?v=` on every page.
    var THEME_KEY = "biotide_theme";
    var CONSENT_KEY = "biotide_cookie_consent";
    // Google Analytics 4 measurement id ("G-XXXXXXXXXX"). Empty = no analytics,
    // no banner, and the footer's "Cookie Settings" link is hidden.
    var GA_ID = "";
    // OpenAI ChatGPT Ads measurement pixel (Ads Manager -> Conversions -> data
    // source). Empty = off. When set, the banner wording covers "our ads" and
    // the privacy policy's Website Analytics section must describe it
    // (see docs/CONSENT.md in the boilerplate for the paragraphs).
    var OAI_PIXEL_ID = "";
    var OAI_PIXEL_DEBUG = false;
    // Cloudflare Web Analytics: cookieless aggregate page views, loaded for
    // everyone outside the consent gate. Paste the site token from Web
    // Analytics -> site -> "Enable with JS Snippet installation" (a DNS-only
    // domain never gets the automatic injection). Empty = off.
    var CF_BEACON_TOKEN = "";

    var sessionConsent = null;
    var ANY_TAG = Boolean(GA_ID) || Boolean(OAI_PIXEL_ID);

    // ---------------------------------------------------------------- regions
    // Regional consent, as far as each region's law allows (reviewed 2026-10-24
    // on snapnutritionai.app; re-check before relying on it):
    //   EEA: both tags opt-in (ePrivacy art. 5(3); EDPB Guidelines 2/2023 treat
    //        cookieless pings as device access too, so Consent Mode "advanced"
    //        is not used). Nothing from Google or OpenAI loads before Accept.
    //   UK:  Google Analytics opt-out under the PECR statistical-purposes
    //        exception (in force 5 Feb 2026), with Google Signals and ad
    //        personalisation off so Google stays a processor. The ad pixel
    //        stays opt-in: the ICO lists ad measurement as needing consent.
    //        The GA4 property's data-sharing settings must be off as well.
    //   CH:  both opt-out (Telecommunications Act art. 45c: inform + refuse).
    //   Everywhere else: both opt-out.
    // An explicit choice in the banner always wins and covers both tags. The
    // region is guessed from the device time zone, then languages, erring
    // towards the EEA when unsure. Google's region-scoped consent default,
    // resolved from the network location, denies analytics storage in the EEA
    // as a second guard. Do Not Track is not honoured (not legally required;
    // say so in the privacy policy).
    var EEA_REGIONS = [
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT",
        "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
        "IS", "LI", "NO"
    ];
    var EEA_LANGUAGES = [
        "de", "fr", "it", "nl", "pl", "sv", "da", "fi", "nb", "nn", "no", "cs", "sk", "hu", "ro",
        "bg", "el", "hr", "sl", "et", "lv", "lt", "mt", "ga", "is", "lb", "fo", "eu", "ca", "gl"
    ];
    var EEA_TIME_ZONES = [
        "Europe/", "Atlantic/Reykjavik", "Atlantic/Canary", "Atlantic/Madeira", "Atlantic/Azores",
        "Atlantic/Faroe", "Atlantic/Faeroe", "Atlantic/Jan_Mayen", "Arctic/Longyearbyen",
        "Indian/Reunion", "Indian/Mayotte", "America/Martinique", "America/Guadeloupe",
        "America/Cayenne", "America/Marigot", "America/St_Barthelemy", "America/Miquelon"
    ];
    // Checked before the "Europe/" prefix above. Gibraltar, Jersey, Guernsey
    // and the Isle of Man have their own laws and stay under the EEA rules.
    var UK_TIME_ZONES = ["Europe/London", "Europe/Belfast"];
    var CH_TIME_ZONES = ["Europe/Zurich"];

    // Which consent model each tag follows per region.
    var CONSENT_MODEL = {
        eea: { analytics: "opt-in", pixel: "opt-in" },
        uk: { analytics: "opt-out", pixel: "opt-in" },
        ch: { analytics: "opt-out", pixel: "opt-out" },
        other: { analytics: "opt-out", pixel: "opt-out" }
    };

    function detectRegion() {
        var timeZone = "";
        try {
            timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
        } catch (error) {
            return "eea";
        }
        if (!timeZone) return "eea";
        if (UK_TIME_ZONES.indexOf(timeZone) !== -1) return "uk";
        if (CH_TIME_ZONES.indexOf(timeZone) !== -1) return "ch";
        for (var i = 0; i < EEA_TIME_ZONES.length; i++) {
            if (timeZone.indexOf(EEA_TIME_ZONES[i]) === 0) return "eea";
        }
        var languages = (navigator.languages && navigator.languages.length)
            ? navigator.languages
            : [navigator.language || ""];
        for (var j = 0; j < languages.length; j++) {
            var parts = String(languages[j]).toLowerCase().split("-");
            var code = parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "";
            if (code.length === 2 && EEA_REGIONS.indexOf(code) !== -1) return "eea";
            if (parts.length === 1 && EEA_LANGUAGES.indexOf(parts[0]) !== -1) return "eea";
        }
        for (var k = 0; k < languages.length; k++) {
            var tag = String(languages[k]).toLowerCase();
            var tail = tag.split("-").pop().toUpperCase();
            if (tail === "GB" || tag === "cy" || tag === "gd") return "uk";
            if (tail === "CH" || tag === "rm") return "ch";
        }
        return "other";
    }

    var region = detectRegion();
    var model = CONSENT_MODEL[region];

    // ---------------------------------------------------------------- storage
    function readPreference(key) {
        try {
            return localStorage.getItem(key);
        } catch (error) {
            return null;
        }
    }

    function writePreference(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (error) {
            // The current page still honours the choice when storage is unavailable.
        }
    }

    // ------------------------------------------------------------------ theme
    // Three-way toggle (light / dark / system) in the header. The <html> element
    // already carries data-theme from the inline <script> in <head>, so there is
    // no flash; this wires the controls and keeps the stored choice.
    function setupTheme() {
        var html = document.documentElement;
        var controls = Array.prototype.slice.call(document.querySelectorAll('.theme-toggle-group input[name="theme"]'));
        var allowedThemes = ["light", "dark", "system"];

        function applyTheme(theme, moveFocus) {
            if (allowedThemes.indexOf(theme) === -1) theme = "system";
            html.setAttribute("data-theme", theme);
            writePreference(THEME_KEY, theme);

            controls.forEach(function (control) {
                var selected = control.dataset.themeValue === theme;
                control.checked = selected;
                control.closest(".theme-option").classList.toggle("active", selected);
                if (selected && moveFocus) control.focus();
            });
        }

        controls.forEach(function (control) {
            control.addEventListener("change", function () {
                if (control.checked) applyTheme(control.dataset.themeValue, false);
            });
        });

        applyTheme(readPreference(THEME_KEY) || "system", false);
    }

    // ---------------------------------------------------------------- consent
    function getConsent() {
        return readPreference(CONSENT_KEY) || sessionConsent;
    }

    function setConsent(status) {
        sessionConsent = status;
        writePreference(CONSENT_KEY, status);
    }

    // Whether a tag ("analytics" or "pixel") may run right now: an explicit
    // choice always wins; with no choice yet it follows the region's model.
    function tagActive(tag) {
        var consent = getConsent();
        if (consent === "accepted") return true;
        if (consent === "rejected") return false;
        return model[tag] === "opt-out";
    }

    function consentState(analytics) {
        return {
            analytics_storage: analytics,
            ad_storage: "denied",
            ad_user_data: "denied",
            ad_personalization: "denied"
        };
    }

    function loadAnalytics() {
        if (!GA_ID || !tagActive("analytics") || document.getElementById("ga-script")) return;

        window.dataLayer = window.dataLayer || [];
        window.gtag = window.gtag || function () {
            window.dataLayer.push(arguments);
        };

        // Defaults must be queued before the tag loads. Analytics on, ads off,
        // everywhere; then the EEA denied until an explicit Accept, which
        // Google applies from the visitor's network location.
        window.gtag("consent", "default", consentState("granted"));
        var eeaDefault = consentState("denied");
        eeaDefault.region = EEA_REGIONS;
        window.gtag("consent", "default", eeaDefault);
        if (getConsent() === "accepted") {
            window.gtag("consent", "update", consentState("granted"));
        }
        window.gtag("js", new Date());
        // UK visitors who have not accepted are measured under the statistical
        // exception, which needs Google to act only as our processor.
        var statisticsOnly = region === "uk" && getConsent() !== "accepted";
        window.gtag("config", GA_ID, statisticsOnly ? {
            allow_google_signals: false,
            allow_ad_personalization_signals: false
        } : {});

        var script = document.createElement("script");
        script.id = "ga-script";
        script.async = true;
        script.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_ID;
        document.head.appendChild(script);
    }

    // OpenAI's setup snippet. Consent is set to true before init because the
    // SDK honours a denial stored on an earlier visit. The SDK does not count
    // page views on its own.
    function loadPixel() {
        if (!OAI_PIXEL_ID || !tagActive("pixel") || document.getElementById("oaiq-script")) return;

        if (!window.oaiq) {
            var queue = function () {
                queue.q.push(arguments);
            };
            queue.q = [];
            window.oaiq = queue;
        }
        window.oaiq("consent", true);
        window.oaiq("init", { pixelId: OAI_PIXEL_ID, debug: OAI_PIXEL_DEBUG });
        window.oaiq("measure", "page_viewed", {
            type: "contents",
            contents: [{
                id: window.location.pathname,
                name: document.title,
                content_type: "page"
            }]
        });

        var script = document.createElement("script");
        script.id = "oaiq-script";
        script.async = true;
        script.src = "https://bzrcdn.openai.com/sdk/oaiq.min.js";
        document.head.appendChild(script);
    }

    function loadTags() {
        loadAnalytics();
        loadPixel();
    }

    function setupConsent() {
        var banner = document.getElementById("cookie-banner");
        var message = document.getElementById("cookie-message");
        var accept = document.getElementById("cookie-accept");
        var reject = document.getElementById("cookie-reject");
        var settings = document.getElementById("cookie-settings");

        if (!ANY_TAG) {
            // No measurement at all: no banner, and no "Cookie Settings" link.
            if (banner) banner.remove();
            if (settings && settings.parentElement && settings.parentElement.tagName === "LI") {
                settings.parentElement.remove();
            } else if (settings) {
                settings.remove();
            }
            return;
        }
        if (!banner || !message || !accept || !reject || !settings) {
            loadTags();
            return;
        }

        function showBanner(show, focusButton) {
            banner.style.display = show ? "flex" : "none";
            banner.setAttribute("aria-hidden", show ? "false" : "true");
            if (show && focusButton) accept.focus();
        }

        // Three banner variants: opt-in (EEA), mixed (UK: analytics on, ad
        // measurement waits), opt-out notice (everywhere else). The wording
        // mentions ads only when the pixel is configured.
        function renderBanner() {
            var ads = Boolean(OAI_PIXEL_ID);
            if (region === "eea") {
                message.textContent = ads
                    ? "We use cookies for analytics and to measure our ads"
                    : "We use cookies for analytics to improve your experience";
                accept.textContent = "Accept";
                reject.textContent = "Reject";
            } else if (region === "uk") {
                message.textContent = ads
                    ? "We use cookies for analytics, and with your OK to measure our ads"
                    : "We use cookies for analytics to improve your experience";
                accept.textContent = ads ? "Accept" : "OK";
                reject.textContent = ads ? "Reject all" : "Turn off";
            } else {
                message.textContent = ads
                    ? "We use cookies for analytics and to measure our ads"
                    : "We use cookies for analytics to improve your experience";
                accept.textContent = "OK";
                reject.textContent = "Turn off";
            }
        }

        accept.addEventListener("click", function () {
            setConsent("accepted");
            loadTags();
            if (typeof window.gtag === "function") {
                window.gtag("consent", "update", consentState("granted"));
            }
            showBanner(false, false);
        });

        reject.addEventListener("click", function () {
            var analyticsWasLoaded = Boolean(document.getElementById("ga-script"));
            var pixelWasLoaded = Boolean(document.getElementById("oaiq-script"));
            setConsent("rejected");
            showBanner(false, false);

            if (analyticsWasLoaded) {
                window.gtag("consent", "update", consentState("denied"));
            }
            if (pixelWasLoaded && typeof window.oaiq === "function") {
                // Stops measurement and removes the pixel's cookies.
                window.oaiq("consent", false);
            }
            if (analyticsWasLoaded || pixelWasLoaded) {
                window.location.reload();
            }
        });

        settings.addEventListener("click", function (event) {
            event.preventDefault();
            renderBanner();
            showBanner(true, true);
        });

        banner.addEventListener("keydown", function (event) {
            if (event.key === "Escape") showBanner(false, false);
        });

        renderBanner();
        var consent = getConsent();
        if (consent === "accepted") {
            loadTags();
        } else if (consent === null) {
            // No choice yet: opt-out tags start now, opt-in tags wait for Accept.
            loadTags();
            showBanner(true, false);
        }
    }

    function loadCloudflareBeacon() {
        if (!CF_BEACON_TOKEN || document.getElementById("cf-beacon")) return;
        var script = document.createElement("script");
        script.id = "cf-beacon";
        script.type = "module";
        script.src = "https://static.cloudflareinsights.com/beacon.min.js";
        script.setAttribute("data-cf-beacon", JSON.stringify({ token: CF_BEACON_TOKEN }));
        document.head.appendChild(script);
    }

    // ----------------------------------------------------------------- events
    // Custom GA event. A no-op whenever the tag is not loaded (EEA before
    // Accept, after Reject, no GA_ID).
    function track(name, params) {
        if (tagActive("analytics") && typeof window.gtag === "function") {
            window.gtag("event", name, params || {});
        }
    }

    function setupAnalyticsEvents() {
        // Every App Store link: `app_store_click` (mark it as a key event in
        // GA4 admin). The pixel gets it as a custom event: reporting only,
        // OpenAI optimises campaigns on standard events alone.
        document.querySelectorAll('a[href*="apps.apple.com"]').forEach(function (link) {
            link.addEventListener("click", function () {
                track("app_store_click", { link_url: link.href, page_path: window.location.pathname });
                if (tagActive("pixel") && typeof window.oaiq === "function") {
                    window.oaiq("measure", "custom", { type: "custom" }, { custom_event_name: "app_store_click" });
                }
            });
        });
        // Any other call to action marked data-cta="<location>".
        document.addEventListener("click", function (event) {
            var link = event.target.closest && event.target.closest("[data-cta]");
            if (link) track("cta_click", { cta_location: link.getAttribute("data-cta"), link_url: link.getAttribute("href") });
        });
    }

    function setFooterYear() {
        var year = document.getElementById("year");
        if (year) year.textContent = new Date().getFullYear();
    }

    // ---------------------------------------------------------------- marquee
    // Endless screenshot strip: clone the single group until the clones cover
    // the strip, so the CSS loop is seamless at any viewport while the gap
    // stays fixed. Skipped under reduced motion, which leaves a plain swipeable
    // strip. Inert without `.marquee` markup.
    function setupMarquee() {
        var strip = document.querySelector(".marquee");
        if (!strip) return;
        var group = strip.querySelector(".marquee-group");
        var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
        var timer = null;
        function fill() {
            strip.querySelectorAll('.marquee-group[aria-hidden="true"]').forEach(function (g) { g.remove(); });
            strip.classList.remove("is-live");
            if (reduce.matches) return;
            var gap = parseFloat(getComputedStyle(strip).columnGap) || 0;
            var unit = group.getBoundingClientRect().width + gap;
            if (!unit) return;
            var clones = Math.ceil(strip.clientWidth / unit);
            for (var i = 0; i < clones; i++) {
                var c = group.cloneNode(true);
                c.setAttribute("aria-hidden", "true");
                c.querySelectorAll("img").forEach(function (img) { img.alt = ""; });
                strip.appendChild(c);
            }
            strip.style.setProperty("--marquee-duration", Math.round(unit / 22) + "s");
            strip.classList.add("is-live");
        }
        fill();
        if ("IntersectionObserver" in window) {
            new IntersectionObserver(function (entries) {
                strip.classList.toggle("is-offscreen", !entries[0].isIntersecting);
            }, { rootMargin: "200px 0px" }).observe(strip);
        }
        window.addEventListener("resize", function () { clearTimeout(timer); timer = setTimeout(fill, 150); });
        if (reduce.addEventListener) reduce.addEventListener("change", fill);
    }

    setupTheme();
    setupConsent();
    loadCloudflareBeacon();
    setupAnalyticsEvents();
    setFooterYear();
    setupMarquee();
})();
