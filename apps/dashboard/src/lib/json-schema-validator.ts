type JsonSchemaType = "object" | "number" | "integer" | "string" | "null";

export type JsonSchema = {
  type?: JsonSchemaType | JsonSchemaType[];
  required?: string[];
  properties?: Record<string, JsonSchema>;
  additionalProperties?: boolean;
  pattern?: string;
  minimum?: number;
  exclusiveMinimum?: number;
};

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const typeList = (schema: JsonSchema): JsonSchemaType[] | null => {
  if (!schema.type) {
    return null;
  }
  return Array.isArray(schema.type) ? schema.type : [schema.type];
};

const allowsNull = (schema: JsonSchema): boolean => {
  const types = typeList(schema);
  return types ? types.includes("null") : false;
};

const includesType = (schema: JsonSchema, type: JsonSchemaType): boolean => {
  const types = typeList(schema);
  if (!types) {
    return true;
  }
  return types.includes(type);
};

const validateNumber = (
  schema: JsonSchema,
  value: number,
  path: string,
  errors: string[],
) => {
  if (!Number.isFinite(value)) {
    errors.push(`${path} must be a finite number.`);
    return;
  }
  if (includesType(schema, "integer") && !Number.isInteger(value)) {
    errors.push(`${path} must be an integer.`);
    return;
  }
  if (
    typeof schema.exclusiveMinimum === "number" &&
    !(value > schema.exclusiveMinimum)
  ) {
    errors.push(
      `${path} must be greater than ${schema.exclusiveMinimum.toString()}.`,
    );
  }
  if (typeof schema.minimum === "number" && value < schema.minimum) {
    errors.push(`${path} must be at least ${schema.minimum.toString()}.`);
  }
};

const validateString = (
  schema: JsonSchema,
  value: string,
  path: string,
  errors: string[],
) => {
  if (!includesType(schema, "string")) {
    errors.push(`${path} must be null.`);
    return;
  }
  if (schema.pattern) {
    const regex = new RegExp(schema.pattern);
    if (!regex.test(value)) {
      errors.push(`${path} must match pattern ${schema.pattern}.`);
    }
  }
};

const validateObject = (
  schema: JsonSchema,
  value: Record<string, unknown>,
  path: string,
  errors: string[],
) => {
  const properties = schema.properties ?? {};
  const required = schema.required ?? [];
  for (const key of required) {
    if (!(key in value)) {
      errors.push(`${path}.${key} is required.`);
    }
  }
  for (const [key, childSchema] of Object.entries(properties)) {
    if (key in value) {
      const nextPath = `${path}.${key}`;
      validateAgainstSchema(childSchema, value[key], nextPath, errors);
    }
  }
  if (schema.additionalProperties === false) {
    const allowedKeys = new Set(Object.keys(properties));
    for (const key of Object.keys(value)) {
      if (!allowedKeys.has(key)) {
        errors.push(`${path}.${key} is not allowed.`);
      }
    }
  }
};

export const validateAgainstSchema = (
  schema: JsonSchema,
  value: unknown,
  path = "$",
  errors: string[] = [],
): string[] => {
  if (value === null) {
    if (!allowsNull(schema)) {
      errors.push(`${path} must not be null.`);
    }
    return errors;
  }
  if (!schema.type) {
    return errors;
  }
  if (includesType(schema, "object") && isObject(value)) {
    validateObject(schema, value, path, errors);
    return errors;
  }
  if (includesType(schema, "number") || includesType(schema, "integer")) {
    if (typeof value !== "number") {
      errors.push(`${path} must be a number.`);
      return errors;
    }
    validateNumber(schema, value, path, errors);
    return errors;
  }
  if (includesType(schema, "string")) {
    if (typeof value !== "string") {
      errors.push(`${path} must be a string.`);
      return errors;
    }
    validateString(schema, value, path, errors);
    return errors;
  }
  errors.push(`${path} has unsupported type.`);
  return errors;
};
