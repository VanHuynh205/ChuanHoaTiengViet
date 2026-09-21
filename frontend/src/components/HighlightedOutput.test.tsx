import { render } from "@testing-library/react";

import { HighlightedOutput } from "./HighlightedOutput";

describe("HighlightedOutput", () => {
  it("marks normalized words without offering a personal meaning form", () => {
    const { container } = render(
      <HighlightedOutput
        text="Hôm nay mình đi học"
        expandedAbbreviations={[{ abbr: "mik", expanded: "mình", start: 8, end: 12 }]}
      />,
    );

    const highlight = container.querySelector(".abbr-highlight");
    expect(highlight).toHaveTextContent("mình");
    expect(highlight).not.toHaveAttribute("role", "button");
    expect(container.querySelector(".abbr-popover")).not.toBeInTheDocument();
  });

  it("does not mark words when normalization only restores diacritics", () => {
    const { container } = render(
      <HighlightedOutput
        text="Hôm nay đi học"
        expandedAbbreviations={[{ abbr: "hom", expanded: "Hôm", start: 0, end: 3 }]}
      />,
    );

    expect(container.querySelector(".abbr-highlight")).not.toBeInTheDocument();
  });

  it("recovers pasted-output highlights when semantic verification changes accents", () => {
    const { container } = render(
      <HighlightedOutput
        text="Hôm nay mình đi học"
        expandedAbbreviations={[{ abbr: "mik", expanded: "minh" }]}
      />,
    );

    expect(container.querySelector(".abbr-highlight")).toHaveTextContent("mình");
  });

  it("does not match short accentless abbreviation metadata inside normal Vietnamese words", () => {
    const { container, rerender } = render(
      <HighlightedOutput
        text="Hiện nay đánh giá sản phẩm gia dụng, gì cũng cần rõ."
        expandedAbbreviations={[{ abbr: "j", expanded: "gì" }]}
      />,
    );

    expect(container.querySelectorAll(".abbr-highlight")).toHaveLength(1);

    rerender(
      <HighlightedOutput
        text="Hiện nay đánh giá sản phẩm gia dụng."
        expandedAbbreviations={[{ abbr: "j", expanded: "gi" }]}
      />,
    );

    expect(container.querySelector(".abbr-highlight")).not.toBeInTheDocument();
  });

  it("uses backend span offsets instead of searching for the first matching expansion", () => {
    const text = "đăng ký trước, đăng ký sau";
    const start = text.lastIndexOf("đăng ký");
    const { container } = render(
      <HighlightedOutput
        text={text}
        expandedAbbreviations={[{ abbr: "dk", expanded: "đăng ký", start, end: start + "đăng ký".length }]}
      />,
    );

    const highlight = container.querySelector(".abbr-highlight");
    expect(highlight?.previousSibling?.textContent).toBe("đăng ký trước, ");
    expect(highlight).toHaveTextContent("đăng ký");
  });
});
