import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { LiveNormalizeResponse } from "../types";
import { NormalizedOutputPane } from "./NormalizedOutputPane";

const data: LiveNormalizeResponse = {
  primaryOutput: "hom nay dang ky hoc phan",
  variants: [
    {
      id: "variant-0",
      output: "hom nay dang ky hoc phan",
      resolutions: [],
      isPrimary: true,
    },
  ],
  ambiguities: [],
  pendingSubmissions: [],
  warnings: [],
  errorTypes: ["PHRASE"],
  latencyMs: 10,
  phraseMatches: [
    {
      start: 2,
      end: 4,
      matched: "dk hp",
      expanded: "dang ky hoc phan",
      confidence: 1,
      source: "override",
    },
  ],
};

describe("NormalizedOutputPane", () => {
  it("keeps the previous reading surface mounted while refreshing and disables stale copying", () => {
    const { rerender } = render(<NormalizedOutputPane data={data} originalText="first" isLoading={false} isSyncing={false} error={null} />);
    const output = screen.getByTestId("primary-output");
    output.scrollTop = 200;
    rerender(<NormalizedOutputPane data={null} originalText="second" isLoading={true} isSyncing={false} error={null} />);
    expect(screen.getByTestId("primary-output")).toBe(output);
    expect(output.scrollTop).toBe(200);
    expect(screen.getByRole("button", { name: "Sao chép kết quả chuẩn hóa" })).toBeDisabled();
    expect(screen.getByText(/Kết quả trước đó/)).toBeInTheDocument();
    rerender(<NormalizedOutputPane data={{ ...data, primaryOutput: "second result" }} originalText="second" isLoading={false} isSyncing={false} error={null} />);
    expect(screen.getByTestId("primary-output")).toBe(output);
    expect(screen.getByRole("button", { name: "Sao chép kết quả chuẩn hóa" })).toBeEnabled();
    rerender(<NormalizedOutputPane data={null} originalText="" isLoading={false} isSyncing={false} error={null} />);
    expect(screen.queryByTestId("primary-output")).not.toBeInTheDocument();
    expect(screen.getByTestId("normalize-status")).toHaveTextContent("Chờ văn bản");
  });
  it("copies only plain text when the comparison contains an insertion marker", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<NormalizedOutputPane originalText="bao giờ đi" data={{ ...data, primaryOutput: "bao giờ đi?",
      changes: [{ id: "q", kinds: ["punctuation"], reason: "explicit_question_opening",
        originalStart: 10, originalEnd: 10, outputStart: 10, outputEnd: 11, originalText: "", outputText: "?" }],
    }} isLoading={false} isSyncing={false} error={null} />);
    expect(screen.getByTestId("output-change-q")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sao chép kết quả chuẩn hóa" }));
    expect(writeText).toHaveBeenCalledWith("bao giờ đi?");
  });
  it("copies the normalized output text to the clipboard", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(
      <NormalizedOutputPane
        data={data}
        isLoading={false}
        isSyncing={false}
        error={null}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Sao chép kết quả chuẩn hóa" }));

    expect(writeText).toHaveBeenCalledWith(data.primaryOutput);
    expect(screen.getByRole("button", { name: "Sao chép kết quả chuẩn hóa" })).toHaveTextContent(
      "Đã sao chép",
    );
  });

  it("keeps phrase matches collapsed until the user opens them", async () => {
    const user = userEvent.setup();
    render(
      <NormalizedOutputPane
        data={data}
        isLoading={false}
        isSyncing={false}
        error={null}
      />,
    );

    const phraseMatches = screen.getByTestId("phrase-matches") as HTMLDetailsElement;
    expect(phraseMatches.open).toBe(false);

    await user.click(screen.getByText("Cụm từ đã ghép"));

    expect(phraseMatches.open).toBe(true);
    expect(screen.getByTestId("phrase-match")).toHaveTextContent("dk hp");
  });

  it("shows the AI verification scope without presenting confidence as accuracy", () => {
    render(
      <NormalizedOutputPane
        data={{
          ...data,
          semanticStatus: "partial",
          semanticVerifiedChunks: 1,
          semanticTotalChunks: 3,
          semanticConfidence: 0.99,
        }}
        isLoading={false}
        isSyncing={false}
        error={null}
      />,
    );

    expect(screen.getByTestId("semantic-status")).toHaveTextContent(
      "AI: Đã kiểm tra một phần (1/3 phần)",
    );
    expect(screen.getByTestId("semantic-status")).not.toHaveTextContent("99%");
  });

  it("explains that a normalized meaning is an AI inference", () => {
    render(<NormalizedOutputPane data={{ ...data, semanticStatus: "uncertain",
      semanticStatusReason: "ai_inferred_meaning" }}
      isLoading={false} isSyncing={false} error={null} />);
    expect(screen.getByTestId("semantic-status")).toHaveTextContent("nghĩa AI suy đoán");
  });

  it("marks unresolved meanings without rendering a variant chooser", () => {
    render(
      <NormalizedOutputPane
        data={{
          ...data,
          ambiguities: [
            {
              id: "dk:0",
              abbr: "dk",
              token_index: 2,
              options: ["đăng ký", "đúng không"],
              selected: "dk",
            },
          ],
          variants: [],
        }}
        isLoading={false}
        isSyncing={false}
        error={null}
      />,
    );

    expect(screen.getByTestId("uncertainty-notice")).toHaveTextContent("dk");
    expect(screen.queryByTestId("variant-list")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ambiguity-list")).not.toBeInTheDocument();
  });

  it("renders output highlights with plain-text copy unchanged", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    const user = userEvent.setup();
    render(
      <NormalizedOutputPane
        originalText="toi di pk"
        data={{
          ...data,
          primaryOutput: "Tôi đi phải không",
          changes: [
            {
              id: "teencode-7-7",
              kinds: ["teencode"],
              originalStart: 7,
              originalEnd: 9,
              outputStart: 7,
              outputEnd: 17,
              originalText: "pk",
              outputText: "phải không",
            },
          ],
        }}
        isLoading={false}
        isSyncing={false}
        error={null}
      />,
    );

    expect(screen.getByTestId("primary-output")).toHaveTextContent("phải không");
    expect(screen.getByTestId("output-change-teencode-7-7")).toHaveTextContent("phải không");
    expect(screen.getAllByText("Teencode/viết tắt").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Sao chép kết quả chuẩn hóa" }));
    expect(screen.getByRole("button", { name: "Sao chép kết quả chuẩn hóa" })).toBeInTheDocument();
  });

  it("keeps change legend labels aligned with their swatch kinds", () => {
    render(
      <NormalizedOutputPane
        originalText="toi di pk"
        data={{
          ...data,
          primaryOutput: "Tôi đi phải không?",
          changes: [
            {
              id: "teencode-1",
              kinds: ["teencode"],
              originalStart: 7,
              originalEnd: 9,
              outputStart: 7,
              outputEnd: 17,
              originalText: "pk",
              outputText: "phải không",
            },
            {
              id: "punctuation-1",
              kinds: ["punctuation"],
              originalStart: 9,
              originalEnd: 9,
              outputStart: 17,
              outputEnd: 18,
              originalText: "",
              outputText: "?",
            },
          ],
        }}
        isLoading={false}
        isSyncing={false}
        error={null}
      />,
    );

    const legend = screen.getByLabelText("Chú giải loại thay đổi");
    expect(legend.querySelector(".change-swatch--teencode")).toBeInTheDocument();
    expect(legend).toHaveTextContent("Teencode/viết tắt");
    expect(legend.querySelector(".change-swatch--punctuation")).toBeInTheDocument();
    expect(legend).toHaveTextContent("Dấu câu");
  });

  it("keeps the legend swatch color aligned with its output highlight", () => {
    render(
      <NormalizedOutputPane
        originalText="toi di pk"
        data={{
          ...data,
          primaryOutput: "Tôi đi phải không",
          changes: [{
            id: "teencode-7-7",
            kinds: ["teencode"],
            originalStart: 7,
            originalEnd: 9,
            outputStart: 7,
            outputEnd: 17,
            originalText: "pk",
            outputText: "phải không",
          }],
        }}
        isLoading={false}
        isSyncing={false}
        error={null}
      />,
    );

    const highlight = screen.getByTestId("output-change-teencode-7-7");
    const swatch = document.querySelector(".change-swatch--teencode");
    expect(swatch).toBeInTheDocument();
    expect((swatch as HTMLElement).style.backgroundColor).toBe(
      (highlight as HTMLElement).style.backgroundColor,
    );
  });
});
