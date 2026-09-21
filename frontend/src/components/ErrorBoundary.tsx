import { Component, type ErrorInfo, type ReactNode } from "react";

type ErrorBoundaryProps = {
  children: ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
};

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("React render error", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="app-error" role="alert">
          <div>
            <p className="app-error__eyebrow">Không thể hiển thị giao diện</p>
            <h1>Đã có lỗi xảy ra.</h1>
            <p>Hãy tải lại trang để khởi tạo lại phiên làm việc.</p>
            <button type="button" onClick={() => window.location.reload()}>
              Tải lại
            </button>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}
