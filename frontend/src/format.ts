const istDateTime = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});

export function formatIstDateTime(value: string | number | Date) {
  return `${istDateTime.format(new Date(value))} IST`;
}
