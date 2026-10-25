package org.veritr1x.bunker;

import java.math.BigDecimal;
import java.util.Locale;

/** Run on the JVM with the compiled ShopPrices class; no Android device needed. */
public final class ShopPricesTest {
    private static int checks;
    private static void equal(String expected, String actual) {
        checks++;
        String compact = actual.replace(" ", "").replace("\u00a0", "").replace("\u202f", "");
        if (!expected.equals(compact)) throw new AssertionError(expected + " != " + actual);
    }
    private static String price(String yen, String tag) {
        return ShopPrices.formatYen(new BigDecimal(yen), Locale.forLanguageTag(tag));
    }
    public static void main(String[] args) {
        equal("2,11€", price("370", "fr-FR"));
        equal("2,11€", price("370", "de-DE"));
        equal("$2.37", price("370", "en-US"));
        equal("0,68€", price("120", "fr-FR"));
        equal("$0.77", price("120", "en-US"));
        equal("0,29€", price("50", "fr-FR")); // half-up, not half-even
        equal("57,00€", price("10000", "fr-FR"));
        equal("$64.00", price("10000", "en-US"));
        equal("0,00€", price("0", "fr-FR"));
        equal("2,11$US", price("330", "fr-US")); // region chooses USD despite French language
        for (String tag : new String[]{"ja-JP", "en-GB", "fr-CA", "fr", "und"}) {
            String digits = price("370", tag).replaceAll("[^0-9]", "");
            equal("370", digits); // no conversion for currencies without an authorized rate
        }
        Locale previous = Locale.getDefault();
        try {
            Locale.setDefault(Locale.FRANCE);
            equal("2,11€", ShopPrices.formatDecimal(2 << 16, 0, 37000));
            equal("-2,11€", ShopPrices.formatDecimal(0x80000000, 0, 370));
            Locale.setDefault(Locale.US);
            equal("$2.37", ShopPrices.formatDecimal(0, 0, 370));
            Locale.setDefault(Locale.JAPAN);
            equal("79228162514264337593543950335",
                    ShopPrices.formatDecimal(0, -1, -1L).replaceAll("[^0-9]", ""));
        } finally {
            Locale.setDefault(previous);
        }
        System.out.println(checks + " offline price checks passed");
    }
}
