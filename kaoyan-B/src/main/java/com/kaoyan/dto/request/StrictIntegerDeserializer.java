package com.kaoyan.dto.request;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonToken;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonDeserializer;
import java.io.IOException;

/** Mutation guards must not silently truncate fractions or coerce strings into integers. */
public class StrictIntegerDeserializer extends JsonDeserializer<Integer> {
    @Override
    public Integer deserialize(JsonParser parser, DeserializationContext context) throws IOException {
        if (parser.currentToken() != JsonToken.VALUE_NUMBER_INT)
            return (Integer) context.handleUnexpectedToken(Integer.class, parser);
        return parser.getIntValue();
    }
}
