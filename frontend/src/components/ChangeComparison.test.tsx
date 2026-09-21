import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { ChangeComparison } from "./ChangeComparison";

it("uses explicit spelling provenance for highlight and reason tooltip", () => {
  render(<ChangeComparison originalText="đăn ký" outputText="Đăng ký" changes={[{
    id: "typo", kinds: ["spelling"], reason: "known_typo", confidence: .99,
    originalStart: 0, originalEnd: 6, outputStart: 0, outputEnd: 7,
    originalText: "đăn ký", outputText: "Đăng ký",
  }]} />);
  for (const side of ["original", "output"]) {
    const mark = screen.getByTestId(`${side}-change-typo`);
    expect(mark).toHaveClass("change-highlight--spelling");
    expect(mark).toHaveAttribute("title", expect.stringContaining("Lỗi gõ đã có trong bộ quy tắc"));
    expect(mark).toHaveAttribute("title", expect.stringContaining("99%"));
  }
});

it("keeps every legend kind visible when a change has overlapping provenance", () => {
  render(<ChangeComparison originalText="dk" outputText="đăng ký" changes={[{
    id: "overlap", kinds: ["ai", "teencode"], source: "ai_context",
    originalStart: 0, originalEnd: 2, outputStart: 0, outputEnd: 7,
    originalText: "dk", outputText: "đăng ký",
  }]} />);

  const mark = screen.getByTestId("output-change-overlap");
  expect(mark).toHaveClass("change-highlight--ai", "change-highlight--teencode");
  expect(mark).toHaveStyle({
    backgroundImage: "linear-gradient(90deg, rgba(15, 118, 110, 0.12) 0%, rgba(15, 118, 110, 0.12) 50%, rgba(14, 116, 144, 0.2) 50%, rgba(14, 116, 144, 0.2) 100%)",
  });
  expect(screen.getByText("AI theo ngữ cảnh")).toBeInTheDocument();
  expect(screen.getByText("Teencode/viết tắt")).toBeInTheDocument();
});

it("renders an empty-source insertion marker and highlights only the new character", () => {
  render(<ChangeComparison originalText="bao giờ đi" outputText="bao giờ đi?" changes={[{
    id: "q", kinds: ["punctuation"], reason: "explicit_question_opening",
    originalStart: 10, originalEnd: 10, outputStart: 10, outputEnd: 11,
    originalText: "", outputText: "?",
  }]} />);
  const marker = screen.getByTestId("original-change-q");
  expect(marker).toHaveAccessibleName(/Vị trí thêm/);
  expect(marker.textContent).toBe("");
  expect(screen.getByTestId("output-change-q")).toHaveTextContent("?");
  // Markers and highlight markup do not add characters to either plain-text pane.
  expect(within(screen.getByTestId("comparison-original")).getByText("bao giờ đi").textContent).toBe("bao giờ đi");
  expect(screen.getByTestId("output-change-q").parentElement?.textContent).toBe("bao giờ đi?");
});

it("keeps code-point offsets correct after an emoji", () => {
  render(<ChangeComparison originalText="😀 đăn ký" outputText="😀 đăng ký" changes={[{
    id: "unicode", kinds: ["spelling"], reason: "known_typo", confidence: .99,
    originalStart: 2, originalEnd: 8, outputStart: 2, outputEnd: 9,
    originalText: "đăn ký", outputText: "đăng ký",
  }]} />);
  expect(screen.getByTestId("original-change-unicode")).toHaveTextContent("đăn ký");
  expect(screen.getByTestId("output-change-unicode")).toHaveTextContent("đăng ký");
});
