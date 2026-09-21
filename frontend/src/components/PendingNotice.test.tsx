import { render, screen } from "@testing-library/react";

import { PendingNotice } from "./PendingNotice";

describe("PendingNotice", () => {
  it("shows pending context without asking the user for a meaning", () => {
    render(
      <PendingNotice
        submissions={[
          {
            abbr: "vch",
            status: "PENDING_CREATED",
            pending_id: "pending-vch",
            has_suggested: false,
            needs_user_meaning: true,
          },
        ]}
      />,
    );

    expect(screen.getByTestId("pending-notice")).toHaveTextContent("vch");
    expect(screen.queryByPlaceholderText("Nhập nghĩa mới")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Gửi nghĩa" })).not.toBeInTheDocument();
  });

  it("hides when there are no pending abbreviations", () => {
    render(<PendingNotice submissions={[]} />);

    expect(screen.queryByTestId("pending-notice")).not.toBeInTheDocument();
  });
});
