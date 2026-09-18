export const parseDateOnly = (value) => {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
};

export const dateOnly = (date) => [
  date.getFullYear(),
  String(date.getMonth() + 1).padStart(2, '0'),
  String(date.getDate()).padStart(2, '0'),
].join('-');

export const addDays = (value, days) => {
  const date = parseDateOnly(value);
  date.setDate(date.getDate() + days);
  return dateOnly(date);
};
