import { useState } from "react";
import { createUserWithEmailAndPassword } from "firebase/auth";
import { auth } from "../firebase";

function Register({ onRegistered, switchToLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    setError("");

    if (password.length < 6) {
      setError("Password must contain at least 6 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const result = await createUserWithEmailAndPassword(
        auth,
        email,
        password
      );

      onRegistered(result.user);
    } catch (err) {
      console.error(err);

      switch (err.code) {
        case "auth/email-already-in-use":
          setError("An account with this email already exists.");
          break;
        case "auth/invalid-email":
          setError("Please enter a valid email address.");
          break;
        case "auth/weak-password":
          setError("Password is too weak.");
          break;
        default:
          setError("Registration failed. Please try again.");
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
          <div className="brand-icon">S</div>

          <div>
            <h1>Sentinexis</h1>
            <span>Self-Healing AIOps Platform</span>
          </div>
        </div>

        <div className="auth-card">

          <div className="auth-header">
            <div className="status-dot"></div>

            <p className="eyebrow">
              CREATE ACCOUNT
            </p>

            <h2>Join Sentinexis</h2>

            <p>
              Create your secure operator account.
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
              <label>Password</label>

              <input
                type="password"
                placeholder="Minimum 6 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <div className="input-group">
              <label>Confirm password</label>

              <input
                type="password"
                placeholder="Repeat your password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
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
                  Creating account...
                </>
              ) : (
                <>
                  Create account
                  <span>→</span>
                </>
              )}
            </button>

          </form>

          <div className="auth-divider">
            <span>ALREADY HAVE AN ACCOUNT?</span>
          </div>

          <button
            className="secondary-button"
            onClick={switchToLogin}
          >
            Back to sign in
          </button>

        </div>

        <div className="security-footer">
          <span>🔒</span>
          Protected by Firebase Authentication
        </div>

      </div>
    </div>
  );
}

export default Register;
