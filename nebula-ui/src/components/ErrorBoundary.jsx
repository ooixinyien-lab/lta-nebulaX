import React from "react";

/**
 * Keep a render-time failure visible in the production bundle instead of
 * leaving the root element blank. Network data errors are handled by the
 * individual hooks; this boundary is for unexpected component/runtime errors.
 */
export default class ErrorBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ForRail UI render failure", error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    const message = error instanceof Error ? error.message : String(error);
    const stack = error instanceof Error ? error.stack : "";

    return (
      <main
        role="alert"
        className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-8"
      >
        <section className="w-full max-w-2xl rounded-xl border border-rose-800 bg-rose-950/40 p-6 shadow-2xl">
          <p className="text-xs font-mono uppercase tracking-wider text-rose-300">
            ForRail UI diagnostic
          </p>
          <h1 className="mt-2 text-xl font-bold text-rose-200">
            The network map could not render
          </h1>
          <p className="mt-2 text-sm text-slate-300">
            The page stopped while rendering. Reload after checking the diagnostic below.
          </p>
          <pre
            data-testid="render-error-message"
            className="mt-4 overflow-auto rounded-lg border border-rose-900 bg-slate-950/80 p-3 text-xs text-rose-200 whitespace-pre-wrap"
          >
            {message}
          </pre>
          {stack && (
            <details className="mt-3 text-xs text-slate-400">
              <summary className="cursor-pointer">Show stack trace</summary>
              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap">{stack}</pre>
            </details>
          )}
          <button
            type="button"
            onClick={this.handleReload}
            className="mt-5 rounded-lg bg-cyan-500 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-cyan-400"
          >
            Reload network map
          </button>
        </section>
      </main>
    );
  }
}
