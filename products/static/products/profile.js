const state = {
    profile: {
        name: "",
        phone: "",
        address: "",
        pincode: ""
    }
};

const formEl = document.getElementById("profileForm");
const nameInputEl = document.getElementById("profileName");
const phoneInputEl = document.getElementById("profilePhone");
const profileStatusEl = document.getElementById("profileStatus");
const profileBtnEl = document.getElementById("profileBtn");
const cartCountEl = document.getElementById("cartCount");

function setProfileButtonState(label = "Save Profile", ready = false) {
    if (!profileBtnEl) return;
    profileBtnEl.setAttribute("title", label);
    profileBtnEl.setAttribute("aria-label", label);
    profileBtnEl.dataset.profileReady = ready ? "true" : "false";
}

function setStatus(message, ok = false) {
    if (!profileStatusEl) return;
    profileStatusEl.textContent = message || "";
    profileStatusEl.classList.toggle("ok", Boolean(ok));
}

function generateCartPhone() {
    const base = Math.floor(1000000000 + Math.random() * 9000000000);
    return `9${String(base).slice(0, 9)}`;
}

function getOrCreateCartPhone() {
    let cartPhone = localStorage.getItem("thathwamasi_cart_phone");
    if (!cartPhone) {
        cartPhone = generateCartPhone();
        localStorage.setItem("thathwamasi_cart_phone", cartPhone);
    }
    return cartPhone;
}

async function apiGet(url) {
    const res = await fetch(url);
    const raw = await res.text();
    let data;
    try {
        data = raw ? JSON.parse(raw) : {};
    } catch {
        throw new Error(`Server returned non-JSON response (${res.status}).`);
    }
    if (!res.ok) throw new Error(data.error || data.detail || `Request failed (${res.status})`);
    return data;
}

async function refreshCartCount() {
    if (!cartCountEl) return;
    const cartPhone = getOrCreateCartPhone();
    if (!cartPhone) {
        cartCountEl.textContent = "0";
        return;
    }
    try {
        const cart = await apiGet(`/api/cart/view/?phone=${encodeURIComponent(cartPhone)}`);
        const count = Number(cart.total_items || 0);
        cartCountEl.textContent = Number.isFinite(count) ? String(count) : "0";
    } catch {
        cartCountEl.textContent = "0";
    }
}

function readProfile() {
    const raw = localStorage.getItem("thathwamasi_profile");
    if (!raw) return;
    try {
        const profile = JSON.parse(raw);
        state.profile = {
            name: profile.name || "",
            phone: profile.phone || "",
            address: profile.address || "",
            pincode: profile.pincode || ""
        };
    } catch (error) {
        console.error(error);
    }

    if (state.profile.name && state.profile.phone) {
        setProfileButtonState(`Saved profile for ${state.profile.name}`, true);
    }
}

function fillForm() {
    if (nameInputEl) nameInputEl.value = state.profile.name;
    if (phoneInputEl) phoneInputEl.value = state.profile.phone;
}

function persistProfile() {
    localStorage.setItem("thathwamasi_profile", JSON.stringify(state.profile));
    localStorage.setItem("thathwamasi_checkout_phone", state.profile.phone);
    setProfileButtonState(`Saved profile for ${state.profile.name}`, true);
}

function saveProfile(event) {
    event.preventDefault();
    state.profile.name = (nameInputEl.value || "").trim();
    state.profile.phone = (phoneInputEl.value || "").trim();

    if (!state.profile.name || !state.profile.phone) {
        setStatus("Enter both name and mobile number.");
        return;
    }

    if (!/^\d{10,15}$/.test(state.profile.phone)) {
        setStatus("Enter a valid mobile number.");
        return;
    }

    persistProfile();
    setStatus("Profile saved. Checkout and order details will use this number.", true);
}

function focusProfileForm() {
    if (nameInputEl) {
        nameInputEl.focus();
        nameInputEl.select();
    }
}

function bootstrap() {
    setProfileButtonState();
    readProfile();
    fillForm();
    refreshCartCount().catch(() => {});
}

if (formEl) {
    formEl.addEventListener("submit", saveProfile);
}

if (profileBtnEl) {
    profileBtnEl.addEventListener("click", focusProfileForm);
}

bootstrap();
