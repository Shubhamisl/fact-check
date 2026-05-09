import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import type { FactCheckReport } from "./types";

const completeReport: FactCheckReport = {
  file_name: "trap.pdf",
  scan_mode: "focused",
  summary: {
    total: 1,
    verified: 0,
    inaccurate: 1,
    false_or_unsupported: 0,
  },
  claims: [
    {
      claim: {
        id: "claim-1",
        text: "The moon is made of green cheese.",
        page_number: 2,
        claim_type: "factual",
        topic: "Astronomy",
        importance: "high",
      },
      verdict: "Inaccurate",
      corrected_fact: "The Moon is made mostly of silicate rock and metal.",
      confidence: "High",
      reasoning: "Current lunar samples and mission evidence contradict the claim.",
      sources: [
        {
          title: "NASA Moon facts",
          url: "https://example.test/moon",
          snippet: "Lunar samples show rock, dust, and mineral composition.",
          published_date: null,
          query: "moon composition",
        },
        {
          title: "Lunar sample summary",
          url: "https://example.test/samples",
          snippet: "Apollo samples are basalt, breccia, and regolith.",
          published_date: null,
          query: "apollo lunar samples",
        },
      ],
      search_queries: ["moon composition"],
    },
  ],
};

function pdfFile() {
  return new File(["%PDF-1.4"], "trap.pdf", { type: "application/pdf" });
}

function namedPdfFile(name: string) {
  return new File(["%PDF-1.4"], name, { type: "application/pdf" });
}

function jsonResponse(payload: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });

  return { promise, resolve };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("App workbench", () => {
  test("initial render shows upload controls and an empty report state", () => {
    const { container } = render(<App />);

    expect(screen.getByText("Choose a PDF")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Focused" }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Deep Scan" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByRole("button", { name: "Run" })).toBeDisabled();
    expect(screen.getByText("No report yet")).toBeInTheDocument();
    expect(
      screen.getByText(/choose a pdf and run the pipeline/i),
    ).toBeInTheDocument();
    expect(
      container.querySelector('input[type="file"]'),
    ).toBeInTheDocument();
  });

  test("selecting a PDF runs the job API flow and renders the completed report", async () => {
    const user = userEvent.setup();
    const createJob = deferred<Response>();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input, init) => {
        const url = input.toString();

        if (url.endsWith("/api/jobs")) {
          expect(init?.method).toBe("POST");
          expect(init?.body).toBeInstanceOf(FormData);
          return createJob.promise;
        }

        if (url.endsWith("/api/jobs/job_123")) {
          return jsonResponse({ status: "complete", progress: 100, report: completeReport });
        }

        throw new Error(`Unexpected fetch: ${url}`);
      });

    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]');

    expect(input).toBeInstanceOf(HTMLInputElement);
    await user.upload(input as HTMLInputElement, pdfFile());

    const runButton = screen.getByRole("button", { name: "Run" });
    expect(runButton).toBeEnabled();

    await user.click(runButton);
    expect(screen.getAllByText("Running")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Running" })).toBeDisabled();

    createJob.resolve(
      new Response(JSON.stringify({ job_id: "job_123" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    expect(await screen.findByRole("heading", { name: "trap.pdf" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0].toString()).toBe(
      "http://localhost:8000/api/jobs",
    );
    expect(fetchMock.mock.calls[1][0].toString()).toBe(
      "http://localhost:8000/api/jobs/job_123",
    );

    const claimRow = screen
      .getByText("The moon is made of green cheese.")
      .closest("tr");

    expect(claimRow).not.toBeNull();
    expect(within(claimRow as HTMLTableRowElement).getByText("Inaccurate")).toBeInTheDocument();
    expect(
      within(claimRow as HTMLTableRowElement).getByText(
        "The Moon is made mostly of silicate rock and metal.",
      ),
    ).toBeInTheDocument();
    expect(within(claimRow as HTMLTableRowElement).getAllByRole("cell")[4]).toHaveTextContent(
      "2",
    );
  });

  test("expanding a result shows reasoning and source details", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = input.toString();

      if (url.endsWith("/api/jobs")) {
        return jsonResponse({ job_id: "job_123" });
      }

      if (url.endsWith("/api/jobs/job_123")) {
        return jsonResponse({ status: "complete", progress: 100, report: completeReport });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    const { container } = render(<App />);
    await user.upload(
      container.querySelector('input[type="file"]') as HTMLInputElement,
      pdfFile(),
    );
    await user.click(screen.getByRole("button", { name: "Run" }));

    const expandButton = await screen.findByRole("button", { name: "Expand" });
    await user.click(expandButton);

    const details = screen.getByRole("region", { name: "Claim details" });
    expect(
      within(details).getByText(
        "Current lunar samples and mission evidence contradict the claim.",
      ),
    ).toBeInTheDocument();
    expect(within(details).getByRole("link", { name: "NASA Moon facts" })).toHaveAttribute(
      "href",
      "https://example.test/moon",
    );
    expect(within(details).getByText(/Apollo samples are basalt/i)).toBeInTheDocument();
  });

  test("shows a JSON download button after a report renders", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = input.toString();

      if (url.endsWith("/api/jobs")) {
        return jsonResponse({ job_id: "job_123" });
      }

      if (url.endsWith("/api/jobs/job_123")) {
        return jsonResponse({ status: "complete", progress: 100, report: completeReport });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    const { container } = render(<App />);
    await user.upload(
      container.querySelector('input[type="file"]') as HTMLInputElement,
      pdfFile(),
    );
    await user.click(screen.getByRole("button", { name: "Run" }));

    expect(await screen.findByRole("button", { name: "JSON" })).toBeInTheDocument();
  });

  test("clears the old report while a new PDF is running", async () => {
    const user = userEvent.setup();
    const secondCreateJob = deferred<Response>();
    let createJobCalls = 0;

    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = input.toString();

      if (url.endsWith("/api/jobs")) {
        createJobCalls += 1;
        if (createJobCalls === 1) {
          return jsonResponse({ job_id: "job_123" });
        }
        return secondCreateJob.promise;
      }

      if (url.endsWith("/api/jobs/job_123")) {
        return jsonResponse({ status: "complete", progress: 100, report: completeReport });
      }

      throw new Error(`Unexpected fetch: ${url}`);
    });

    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, namedPdfFile("first.pdf"));
    await user.click(screen.getByRole("button", { name: "Run" }));
    expect(await screen.findByRole("heading", { name: "trap.pdf" })).toBeInTheDocument();

    await user.upload(input, namedPdfFile("second.pdf"));
    await user.click(screen.getByRole("button", { name: "Run" }));

    expect(screen.getAllByText("Running")).toHaveLength(2);
    expect(screen.queryByRole("heading", { name: "trap.pdf" })).not.toBeInTheDocument();
  });
});
