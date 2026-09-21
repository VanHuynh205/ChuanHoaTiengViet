import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { LiveVariant } from "../types";
import { VariantCardList } from "./VariantCardList";

const variants: LiveVariant[] = [
  {
    id: "variant-0",
    output: "hôm nay đi đăng ký thẻ ngân hàng phải không",
    resolutions: [{ ambiguity_id: "đk:0", meaning: "đăng ký" }],
    isPrimary: true,
  },
  {
    id: "variant-1",
    output: "hôm nay đi đúng không thẻ ngân hàng phải không",
    resolutions: [{ ambiguity_id: "đk:0", meaning: "đúng không" }],
    isPrimary: false,
  },
];

describe("VariantCardList", () => {
  it("collapses other sentence variants after a selection and can show them again", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const { rerender } = render(
      <VariantCardList
        collapseAfterSelection
        variants={variants}
        selectedVariantId={null}
        onSelect={onSelect}
      />,
    );

    expect(screen.getByTestId("variant-card-variant-0")).toBeInTheDocument();
    expect(screen.getByTestId("variant-card-variant-1")).toBeInTheDocument();

    await user.click(screen.getByTestId("variant-card-variant-1"));
    expect(onSelect).toHaveBeenCalledWith(variants[1]);

    rerender(
      <VariantCardList
        collapseAfterSelection
        variants={variants}
        selectedVariantId="variant-1"
        onSelect={onSelect}
      />,
    );

    expect(screen.queryByTestId("variant-card-variant-0")).not.toBeInTheDocument();
    expect(screen.getByTestId("variant-card-variant-1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xem lại toàn bộ phương án" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Xem lại toàn bộ phương án" }));
    expect(screen.getByTestId("variant-card-variant-0")).toBeInTheDocument();
  });
});
