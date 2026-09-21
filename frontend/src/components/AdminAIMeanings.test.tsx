import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { AdminAIMeanings } from "./AdminAIMeanings";
import { api } from "../lib/api";

vi.mock("../lib/api", () => ({ api: { aiMeanings: vi.fn(), aiMeaningDetail: vi.fn(), moderateAIMeanings: vi.fn() } }));
const row = { id: "one", abbr: "xyz", meaning: "đăng ký", domain: "education", status: "conditional_shared",
  evidence_count: 3, confidence: .85, revision: 4, policy_version: "v1", provider: "fake", model: "fake" };
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.aiMeanings).mockResolvedValue([row]);
  vi.mocked(api.aiMeaningDetail).mockResolvedValue({ candidate: row,
    evidence: [{ context_snippet: "[redacted] xyz học phần", created_at: "today" }],
    audit: [{ id: "a", action: "conditional_shared", actor: "policy", reason: "threshold", revision: 4, created_at: "today" }] });
  vi.mocked(api.moderateAIMeanings).mockResolvedValue({ items: [], cacheStatus: "invalidated" });
});
it("filters, shows redacted context/audit and revokes selected candidates", async () => {
  render(<AdminAIMeanings token="test" />);
  fireEvent.click(await screen.findByRole("button", { name: "Bằng chứng và audit" }));
  expect(await screen.findByText("[redacted] xyz học phần")).toBeInTheDocument();
  expect(screen.getByText(/threshold/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: "Chọn xyz: đăng ký" }));
  fireEvent.change(screen.getByLabelText("Lý do quyết định"), { target: { value: "sai nghĩa" } });
  fireEvent.click(screen.getByRole("button", { name: /Thu hồi mục đã chọn/ }));
  await waitFor(() => expect(api.moderateAIMeanings).toHaveBeenCalledWith("test", ["one"], "revoke", "sai nghĩa"));
  await waitFor(() => expect(screen.getByLabelText("Trạng thái")).not.toBeDisabled());
  fireEvent.change(screen.getByLabelText("Trạng thái"), { target: { value: "needs_review" } });
  await waitFor(() => expect(api.aiMeanings).toHaveBeenLastCalledWith("test", expect.objectContaining({ status: "needs_review" })));
});

it("shows a rejected confirmation without claiming success", async () => {
  vi.mocked(api.moderateAIMeanings).mockRejectedValue(new Error("Revoke competing meanings before confirming"));
  render(<AdminAIMeanings token="test" />);
  fireEvent.click(await screen.findByRole("checkbox"));
  fireEvent.change(screen.getByLabelText("Lý do quyết định"), { target: { value: "checked" } });
  fireEvent.click(screen.getByRole("button", { name: "Xác nhận mục đã chọn" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Revoke competing meanings");
});
