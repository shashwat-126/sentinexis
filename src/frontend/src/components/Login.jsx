import { useState } from "react";
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "../firebase";

function Login({ onLogin, switchToRegister }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    setError("");
    setLoading(true);

    try {
      const result = await signInWithEmailAndPassword(
        auth,
        email,
        password
      );

      onLogin(result.user);
    } catch (err) {
      console.error(err);

      switch (err.code) {
        case "auth/invalid-credential":
          setError("Invalid email or password.");
          break;
        case "auth/user-not-found":
          setError("No account found with this email.");
          break;
        case "auth/wrong-password":
          setError("Incorrect password.");
          break;
        case "auth/too-many-requests":
          setError("Too many attempts. Try again later.");
          break;
        default:
          setError("Login failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-background">
        <div className="grid-overlay"></div>
      </div>

      <div className="auth-container">

        <div className="brand">
          <div className="brand-icon">
            S
          </div>

          <div>
            <h1>Sentinexis</h1>
            <span>Self-Healing AIOps Platform</span>
          </div>
        </div>

        <div className="auth-card">

          <div className="auth-header">
            <div className="status-dot"></div>

            <p className="eyebrow">
              SECURE ACCESS
            </p>

            <h2>Welcome back</h2>

            <p>
              Sign in to monitor and control your
              distributed infrastructure.
            </p>
          </div>

          <form onSubmit={handleSubmit}>

            <div className="input-group">
              <label>Email address</label>

              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="input-group">
              <div className="password-label">
                <label>Password</label>
              </div>

              <input
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {error && (
              <div className="auth-error">
                <span>!</span>
                {error}
              </div>
            )}

            <button
              className="auth-button"
              type="submit"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="button-spinner"></span>
                  Signing in...
                </>
              ) : (
                <>
                  Sign in
                  <span>→</span>
                </>
              )}
            </button>

          </form>

          <div className="auth-divider">
            <span>NEW TO SENTINEXIS?</span>
          </div>

          <button
            className="secondary-button"
            onClick={switchToRegister}
          >
            Create an account
          </button>

        </div>

        <div className="security-footer">
          <span>🔒</span>
          Secured by Firebase Authentication
        </div>

      </div>
    </div>
  );
}

export default Login;
