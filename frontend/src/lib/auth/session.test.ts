import { beforeEach, describe, expect, it } from "vitest";
import {
  clearSession,
  getAccessToken,
  getDevRole,
  getSessionUser,
  setDevRole,
  setSession,
} from "./session";

describe("auth session helpers", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("stores and clears a JWT session", () => {
    expect(getAccessToken()).toBeNull();
    setSession("tok-1", {
      id: "u1",
      email: "a@b.c",
      role: "security_admin",
      name: "Admin",
    });
    expect(getAccessToken()).toBe("tok-1");
    expect(getSessionUser()?.email).toBe("a@b.c");
    clearSession();
    expect(getAccessToken()).toBeNull();
    expect(getSessionUser()).toBeNull();
  });

  it("stores a dev role bypass", () => {
    setDevRole("auditor");
    expect(getDevRole()).toBe("auditor");
  });
});
