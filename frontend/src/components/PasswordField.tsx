import { useState } from "react";
import { Icon } from "./Icon";

export function PasswordField({ value, onChange, testId, autoComplete }: {
  value: string; onChange: (value: string) => void; testId: string; autoComplete: "current-password" | "new-password";
}) {
  const [visible, setVisible] = useState(false);
  return <div className="password-field auth-form__control">
    <Icon name="lock" />
    <input id={testId} data-testid={testId} type={visible ? "text" : "password"} required autoComplete={autoComplete} placeholder="Nhập mật khẩu" value={value} onChange={(event) => onChange(event.target.value)} />
    <button className="password-field__toggle" type="button" aria-label={visible ? "Ẩn mật khẩu" : "Hiện mật khẩu"} aria-pressed={visible} onClick={() => setVisible(!visible)}><Icon name="eye" /></button>
  </div>;
}
