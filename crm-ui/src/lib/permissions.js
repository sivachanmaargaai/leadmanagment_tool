export function canAccessQuotations(user) {
  return user?.role === "Admin" || user?.canAccessQuotations === true;
}
