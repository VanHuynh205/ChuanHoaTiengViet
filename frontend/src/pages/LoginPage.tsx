import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { AuthShell } from "../components/AuthShell";
import { PasswordField } from "../components/PasswordField";
import { Icon } from "../components/Icon";
import { ApiError } from "../lib/api";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await login(identifier, password);
      navigate("/");
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(caughtError.message);
        return;
      }
      setError("Không thể đăng nhập ở thời điểm hiện tại.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      title="Đăng nhập"
      description="Chào mừng bạn quay trở lại với Viet Normalizer."
    >
      <form className="auth-form" aria-busy={submitting} onSubmit={handleSubmit}>
        <div className="auth-form__field">
          <label htmlFor="login-identifier">Email hoặc tên đăng nhập</label>
          <div className="auth-form__control">
            <Icon name="mail" />
            <input id="login-identifier" autoComplete="username" required placeholder="Nhập email hoặc tên đăng nhập" data-testid="login-identifier" value={identifier} onChange={(event) => setIdentifier(event.target.value)} />
          </div>
        </div>
        <div className="auth-form__field">
          <label htmlFor="login-password">Mật khẩu</label>
          <PasswordField value={password} onChange={setPassword} testId="login-password" autoComplete="current-password" />
        </div>
        <div className="auth-form__row">
          <label className="auth-form__remember">
            <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
            <span>Ghi nhớ đăng nhập</span>
          </label>
        </div>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button data-testid="login-submit" type="submit" disabled={submitting}>
          {submitting ? <span className="auth-form__spinner" aria-hidden="true" /> : null}
          <span>{submitting ? "Đang đăng nhập…" : "Vào hệ thống"}</span>
          <Icon name="arrow" />
        </button>
      </form>
      <p className="auth-shell__switch">
        <span className="auth-shell__switch-label">Chưa có tài khoản?</span>
        <Link to="/register" aria-label="Đăng ký">Đăng ký ngay</Link>
      </p>
    </AuthShell>
  );
}
