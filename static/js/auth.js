const auth = {
    _user: null,
    _initPromise: null,

    _setUser(user) {
        this._user = user;
    },

    getUser() {
        return this._user;
    },

    async register(name, email, password) {
        const gmailRegex = /^[a-zA-Z0-9._%+\-]+@gmail\.com$/;
        if (!gmailRegex.test(email)) {
            return { success: false, message: "Email harus menggunakan @gmail.com" };
        }
        const response = await fetch("/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ name, email, password }),
        });

        const data = await response.json();
        if (!response.ok) {
            return { success: false, message: data.message || "Pendaftaran gagal" };
        }

        return { success: true, message: data.message || "Pendaftaran berhasil" };
    },

    async login(identifier, password) {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ identifier, password }),
        });

        const data = await response.json();
        if (!response.ok) {
            this._setUser(null);
            return { success: false, message: data.message || "Login gagal" };
        }

        this._setUser(data.user);
        return { success: true, user: data.user };
    },

    async refreshSession() {
        const response = await fetch("/api/me", {
            method: "GET",
            credentials: "include",
        });

        if (!response.ok) {
            this._setUser(null);
            return null;
        }

        const data = await response.json();
        this._setUser(data.user);
        return data.user;
    },

    async updateProfile(name, email, photoFile) {
        const formData = new FormData();
        formData.append("name", name);
        formData.append("email", email);
        if (photoFile) {
            formData.append("photo", photoFile);
        }

        const response = await fetch("/api/me", {
            method: "PUT",
            credentials: "include",
            body: formData,
        });

        const data = await response.json();
        if (!response.ok) {
            return { success: false, message: data.message || "Gagal memperbarui profil" };
        }

        this._user = data.user;
        this._updateNavUi(data.user);
        return { success: true, user: data.user };
    },

    async logout() {
        try {
            await fetch("/api/logout", { method: "POST", credentials: "include" });
        } catch (_err) {
            // Ignore network errors on logout and still clear local state.
        }

        this._setUser(null);
        window.location.href = "/";
    },

    _updateNavUi(user) {
        const navAuth = document.getElementById("nav-auth");
        const navUser = document.getElementById("nav-user");

        if (navAuth && navUser) {
            if (user) {
                navAuth.classList.add("hidden");
                navUser.classList.remove("hidden");

                const userNameDisplay = document.getElementById("nav-user-name");
                const userInitialDisplay = document.getElementById("nav-user-initial");
                if (userNameDisplay) userNameDisplay.textContent = user.name;
                if (userInitialDisplay) {
                    if (user.photo) {
                        userInitialDisplay.innerHTML = `<img src="${user.photo}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">`;
                    } else {
                        userInitialDisplay.textContent = user.name.charAt(0).toUpperCase();
                    }
                }
            } else {
                navAuth.classList.remove("hidden");
                navUser.classList.add("hidden");
            }
        }
    },

    async init() {
        if (this._initPromise) {
            return this._initPromise;
        }

        this._initPromise = (async () => {
            await this.refreshSession();
            const user = this.getUser();
            this._updateNavUi(user);

            const onDashboard = window.location.pathname.endsWith("/dashboard")
                || window.location.pathname === "/dashboard";

            if (onDashboard && !user) {
                window.location.href = "login";
            }

            return user;
        })();

        return this._initPromise;
    },
};

document.addEventListener("DOMContentLoaded", () => {
    auth.init();
});
