import { BrandMark } from "./BrandMark";
import { Icon } from "./Icon";

export function AuthShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <main className="auth-shell">
      <div className="auth-shell__frame">
        <section className="auth-story" aria-label="Giới thiệu Chuẩn hóa tiếng Việt">
          <span className="auth-story__glow" aria-hidden="true" />
          <span className="auth-story__scape" aria-hidden="true" />
          <div className="auth-story__topline"><span>01 / Bắt đầu</span><span className="auth-story__rule" aria-hidden="true" /><span>Viet Normalizer</span></div>
          <div className="auth-story__lockup">
            <div className="brand-lockup"><BrandMark /><span><strong>VIỆT</strong><br />NORMALIZER</span></div>
            <p className="auth-story__tagline">Chuẩn hóa tiếng Việt. Kết nối tri thức.</p>
          </div>
          <img className="auth-story__art" src="/images/vietnamese-ribbon.png" alt="" fetchPriority="high" />
          <div className="auth-story__copy">
            <h2>Rõ từng chữ.<br />Đúng từng ý.</h2>
            <p>Công cụ chuẩn hóa văn bản tiếng Việt, giúp bạn viết đúng hơn, rõ ràng hơn và chuyên nghiệp hơn.</p>
          </div>
          <p className="auth-story__script" aria-hidden="true">Cùng hướng tới những điều rõ ràng hơn</p>
          <p className="auth-story__footnote">Vì một tiếng Việt<br />rõ ràng hơn mỗi ngày.</p>
        </section>
        <section className="auth-shell__panel" aria-labelledby="auth-title">
          <p className="auth-shell__locale"><Icon name="globe" /> Tiếng Việt</p>
          <div className="auth-shell__form-content">
            <p className="auth-shell__kicker">Không gian viết rõ ràng</p>
            <h1 id="auth-title">{title}</h1>
            <p className="auth-shell__description">{description}</p>
            {children}
          </div>
          <p className="auth-shell__footer"><Icon name="leaf" /> Cùng nhau giữ gìn sự trong sáng của <strong>tiếng Việt</strong>.</p>
        </section>
      </div>
    </main>
  );
}
