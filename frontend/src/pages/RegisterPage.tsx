import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { AuthShell } from "../components/AuthShell";
import { PasswordField } from "../components/PasswordField";
import { Icon } from "../components/Icon";
import { ApiError } from "../lib/api";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await register(username, email, password);
      navigate("/");
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
        return;
      }
      setError("Không thể đăng ký ở thời điểm hiện tại.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      title="Đăng ký"
      description="Bắt đầu không gian viết rõ ràng của bạn."
    >
      <form className="auth-form" aria-busy={submitting} onSubmit={handleSubmit}>
        <div className="auth-form__field">
          <label htmlFor="register-username">Tên đăng nhập</label>
          <div className="auth-form__control">
            <Icon name="user" />
            <input id="register-username" autoComplete="username" required placeholder="Chọn tên đăng nhập" data-testid="register-username" value={username} onChange={(event) => setUsername(event.target.value)} />
          </div>
        </div>
        <div className="auth-form__field">
          <label htmlFor="register-email">Email</label>
          <div className="auth-form__control">
            <Icon name="mail" />
            <input
              id="register-email" autoComplete="email" required placeholder="ban@example.com" data-testid="register-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
        </div>
        <div className="auth-form__field">
          <label htmlFor="register-password">Mật khẩu</label>
          <PasswordField value={password} onChange={setPassword} testId="register-password" autoComplete="new-password" />
        </div>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button data-testid="register-submit" type="submit" disabled={submitting}>
          {submitting ? <span className="auth-form__spinner" aria-hidden="true" /> : null}
          <span>{submitting ? "Đang tạo tài khoản…" : "Tạo tài khoản"}</span>
          <Icon name="arrow" />
        </button>
      </form>
      <p className="auth-shell__switch">
        <span className="auth-shell__switch-label">Đã có tài khoản?</span>
        <Link to="/login" aria-label="Đăng nhập">Đăng nhập ngay</Link>
      </p>
    </AuthShell>
  );
}
