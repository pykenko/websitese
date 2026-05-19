const SESSION_KEY = "berikasih_session";

const auth = {
    _user: null,
    _initPromise: null,

    _setUser(user) {
        const existingUser = this.getUser();
        this._user = user;
        if (user && !user.photo && existingUser && existingUser.id === user.id && existingUser.photo) {
            this._user = { ...user, photo: existingUser.photo };
        }
        if (user) {
            localStorage.setItem(SESSION_KEY, JSON.stringify(this._user));
        } else {
            localStorage.removeItem(SESSION_KEY);
        }
    },

    getUser() {
        if (this._user) {
            return this._user;
        }
        const sessionData = localStorage.getItem(SESSION_KEY);
        if (!sessionData) {
            return null;
        }
        try {
            const parsed = JSON.parse(sessionData);
            this._user = parsed;
            return parsed;
        } catch (_err) {
            localStorage.removeItem(SESSION_KEY);
            return null;
        }
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

    async updateProfile(name, email, photo) {
        const response = await fetch("/api/me", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ name, email }),
        });

        const data = await response.json();
        if (!response.ok) {
            return { success: false, message: data.message || "Gagal memperbarui profil" };
        }

        const updatedUser = { ...data.user };
        if (photo) {
            updatedUser.photo = photo;
        } else {
            const currentUser = this.getUser();
            if (currentUser?.photo) {
                updatedUser.photo = currentUser.photo;
            }
        }

        this._setUser(updatedUser);
        this._updateNavUi(updatedUser);
        return { success: true, user: updatedUser };
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
                if (userInitialDisplay) userInitialDisplay.textContent = user.name.charAt(0).toUpperCase();
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
