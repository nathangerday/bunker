package org.veritr1x.bunker;

import android.util.Log;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.text.NumberFormat;
import java.util.Currency;
import java.util.Locale;

/** Offline display conversions from the bundled JPY prices; never a payment amount. */
final class ShopPrices {
    private ShopPrices() {}

    static void install() {
        try {
            System.loadLibrary("bunkershop");
            if (!installNative()) Log.w("Bunker", "Offline price formatter unavailable; keeping bundled prices");
        } catch (Throwable error) {
            Log.w("Bunker", "Offline price formatter unavailable; keeping bundled prices", error);
        }
    }

    private static native boolean installNative();

    // Called on Unity's thread. Decode the full .NET Decimal without a floating-point conversion.
    static String formatDecimal(int flags, int high, long low) {
        BigInteger magnitude = new BigInteger(Long.toUnsignedString(low))
                .add(BigInteger.valueOf(Integer.toUnsignedLong(high)).shiftLeft(64));
        if (flags < 0) magnitude = magnitude.negate();
        return formatYen(new BigDecimal(magnitude, (flags >>> 16) & 0xff), Locale.getDefault());
    }

    static String formatYen(BigDecimal yen, Locale locale) {
        Currency currency = Currency.getInstance("JPY");
        try {
            Currency regional = Currency.getInstance(locale);
            if (regional != null && (regional.getCurrencyCode().equals("EUR")
                    || regional.getCurrencyCode().equals("USD"))) currency = regional;
        } catch (IllegalArgumentException noRegion) {
            // Language-only and unsupported regions retain the original JPY amount.
        }
        BigDecimal rate;
        switch (currency.getCurrencyCode()) {
            case "EUR": rate = new BigDecimal("0.0057"); break;
            case "USD": rate = new BigDecimal("0.0064"); break;
            default: rate = BigDecimal.ONE;
        }
        int digits = currency.getDefaultFractionDigits();
        BigDecimal converted = yen.multiply(rate).setScale(digits, RoundingMode.HALF_UP);
        NumberFormat format = NumberFormat.getCurrencyInstance(locale);
        format.setCurrency(currency);
        format.setMinimumFractionDigits(digits);
        format.setMaximumFractionDigits(digits);
        format.setRoundingMode(RoundingMode.HALF_UP);
        return format.format(converted);
    }
}
