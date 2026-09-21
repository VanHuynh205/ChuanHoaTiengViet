import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { LiveAmbiguity } from "../types";
import { AmbiguityChoiceList } from "./AmbiguityChoiceList";

const ambiguities: LiveAmbiguity[] = [
  {
    id: "ct:0",
    abbr: "ct",
    token_index: 1,
    options: ["công ty", "chương trình"],
    selected: "công ty",
  },
  {
    id: "đk:0",
    abbr: "đk",
    token_index: 4,
    options: ["đăng ký", "đúng không"],
    selected: "đăng ký",
  },
];

describe("AmbiguityChoiceList", () => {
  it("keeps review mode open after reselecting a meaning until the user exits manually", async () => {
    const user = userEvent.setup();

    render(
      <AmbiguityChoiceList
        ambiguities={ambiguities}
        selectedMeanings={{ "ct:0": "công ty", "đk:0": "đúng không" }}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Chọn lại" })).toBeInTheDocument();
    expect(screen.queryByText("ct")).not.toBeInTheDocument();
    expect(screen.queryByText("đk")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Chọn lại" }));

    const abbreviationButtons = screen.getAllByRole("button");
    expect(abbreviationButtons.map((button) => button.textContent)).toEqual(["Thoát", "đk", "ct"]);

    await user.click(screen.getByRole("button", { name: "đk" }));
    expect(screen.getByRole("button", { name: "đăng ký" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "đúng không" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "đăng ký" }));

    const reviewButtons = screen.getAllByRole("button");
    expect(reviewButtons.map((button) => button.textContent)).toEqual(["Thoát", "đk", "ct"]);
  });

  it("keeps the newest unresolved ambiguity open until a meaning is selected", async () => {
    const onSelect = vi.fn();

    render(
      <AmbiguityChoiceList
        ambiguities={ambiguities}
        selectedMeanings={{ "ct:0": "công ty" }}
        onSelect={onSelect}
      />,
    );

    expect(screen.getByRole("button", { name: "đăng ký" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "đúng không" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Chọn lại" })).not.toBeInTheDocument();
  });

  it("allows leaving review mode with the exit button", async () => {
    const user = userEvent.setup();

    render(
      <AmbiguityChoiceList
        ambiguities={ambiguities}
        selectedMeanings={{ "ct:0": "công ty", "đk:0": "đúng không" }}
        onSelect={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Chọn lại" }));
    await user.click(screen.getByRole("button", { name: "Thoát" }));

    expect(screen.getByRole("button", { name: "Chọn lại" })).toBeInTheDocument();
  });
  it("keeps custom meaning entry out of the variant chooser", () => {
    render(
      <AmbiguityChoiceList
        ambiguities={ambiguities}
        selectedMeanings={{ "ct:0": "cﾃｴng ty" }}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.queryByLabelText("Thêm nghĩa mới theo ý bạn")).not.toBeInTheDocument();
  });
});
