import { useState } from "react";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { Link, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { InfinityLogo } from "@/src/components/InfinityLogo";
import { Field, PrimaryButton, Screen } from "@/src/components/ui";
import { useAuth } from "@/src/auth-context";
import { fonts, makeStyles, spacing } from "@/src/theme";

export default function Login() {
  const router = useRouter();
  const { login, socialLogin } = useAuth();
  const styles = useStyles();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [socialLoading, setSocialLoading] = useState<"google" | "instagram" | null>(null);

  const submit = async () => {
    if (!email.trim() || !password) {
      setError("Informe e-mail e senha.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const u = await login(email.trim(), password);
      if (!u) throw new Error("Não foi possível validar sua sessão. Tente novamente.");
      router.replace(u.company_id ? "/dashboard" : "/onboarding");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível entrar.");
    } finally {
      setLoading(false);
    }
  };

  const submitSocial = async (provider: "google" | "instagram") => {
    setError("");
    setSocialLoading(provider);
    try {
      const u = await socialLogin(provider);
      if (!u) return;
      router.replace(u.company_id ? "/dashboard" : "/onboarding");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível entrar com esta conta.");
    } finally {
      setSocialLoading(null);
    }
  };

  return (
    <Screen testID="login-screen">
      <KeyboardAwareScrollView
        contentContainerStyle={styles.scroll}
        bottomOffset={24}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.brandRow}>
          <InfinityLogo size={88} />
          <Text style={styles.wordmark}>InovaPro</Text>
          <Text style={styles.slogan}>Conectando você ao mundo</Text>
        </View>

        <View style={styles.form}>
          <Text style={styles.smartTitle}>Comece pelo seu negócio</Text>
          <Text style={styles.smartText}>Conecte uma conta para a InovaPro aproveitar dados autorizados e reduzir perguntas no Diagnóstico 360°.</Text>

          <Pressable
            testID="login-google-button"
            accessibilityRole="button"
            disabled={!!socialLoading}
            onPress={() => submitSocial("google")}
            style={({ pressed }) => [styles.socialButton, pressed && styles.socialPressed]}
          >
            {socialLoading === "google" ? <ActivityIndicator /> : <Text style={styles.googleMark}>G</Text>}
            <View style={styles.socialTextWrap}>
              <Text style={styles.socialLabel}>Continuar com Google</Text>
              <Text style={styles.socialHint}>Conta Google + negócio vinculado, quando autorizado</Text>
            </View>
          </Pressable>

          <Pressable
            testID="login-instagram-button"
            accessibilityRole="button"
            disabled={!!socialLoading}
            onPress={() => submitSocial("instagram")}
            style={({ pressed }) => [styles.socialButton, pressed && styles.socialPressed]}
          >
            {socialLoading === "instagram" ? <ActivityIndicator /> : <Text style={styles.instagramMark}>◎</Text>}
            <View style={styles.socialTextWrap}>
              <Text style={styles.socialLabel}>Continuar com Instagram</Text>
              <Text style={styles.socialHint}>Para contas profissionais Business ou Creator</Text>
            </View>
          </Pressable>

          <View style={styles.dividerRow}>
            <View style={styles.divider} />
            <Text style={styles.dividerText}>ou entre com e-mail</Text>
            <View style={styles.divider} />
          </View>

          <Field
            label="E-mail"
            value={email}
            onChangeText={setEmail}
            placeholder="voce@empresa.com.br"
            keyboardType="email-address"
            testID="login-email-input"
          />
          <Field
            label="Senha"
            value={password}
            onChangeText={setPassword}
            placeholder="Sua senha"
            secure
            testID="login-password-input"
          />
          {error ? (
            <Text style={styles.error} testID="login-error">
              {error}
            </Text>
          ) : null}
          <PrimaryButton label="Entrar" onPress={submit} loading={loading} testID="login-submit-button" />
          <View style={styles.registerRow}>
            <Text style={styles.mutedText}>Ainda não tem conta?</Text>
            <Link href="/(auth)/register" asChild>
              <Pressable testID="login-go-register" accessibilityRole="link" hitSlop={8}>
                <Text style={styles.linkText}>Criar conta</Text>
              </Pressable>
            </Link>
          </View>
        </View>
      </KeyboardAwareScrollView>
    </Screen>
  );
}

const useStyles = makeStyles((colors) => ({
  scroll: { flexGrow: 1, justifyContent: "center", paddingVertical: spacing.xl, gap: spacing.xl },
  brandRow: { alignItems: "center", gap: spacing.xs },
  wordmark: { color: colors.onSurface, fontSize: 30, fontFamily: fonts.display },
  slogan: { color: colors.muted, fontSize: 13, fontFamily: fonts.text },
  form: { gap: spacing.lg },
  smartTitle: { color: colors.onSurface, fontSize: 18, fontFamily: fonts.textBold, textAlign: "center" },
  smartText: { color: colors.onSurfaceSecondary, fontSize: 13, lineHeight: 19, fontFamily: fonts.text, textAlign: "center" },
  socialButton: {
    minHeight: 62, borderRadius: 14, borderWidth: 1, borderColor: colors.borderStrong, backgroundColor: colors.surfaceSecondary,
    flexDirection: "row", alignItems: "center", paddingHorizontal: spacing.lg, gap: spacing.md,
  },
  socialPressed: { opacity: 0.82 },
  socialTextWrap: { flex: 1, gap: 2 },
  socialLabel: { color: colors.onSurface, fontSize: 15, fontFamily: fonts.textSemi },
  socialHint: { color: colors.onSurfaceSecondary, fontSize: 11, fontFamily: fonts.text },
  googleMark: { color: colors.onSurface, fontSize: 22, fontFamily: fonts.textBold, width: 26, textAlign: "center" },
  instagramMark: { color: colors.brandSecondary, fontSize: 28, fontFamily: fonts.textBold, width: 26, textAlign: "center" },
  dividerRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  divider: { flex: 1, height: 1, backgroundColor: colors.divider },
  dividerText: { color: colors.muted, fontSize: 11, fontFamily: fonts.textMedium },
  error: { color: colors.error, fontSize: 13, fontFamily: fonts.textMedium, textAlign: "center" },
  registerRow: { flexDirection: "row", justifyContent: "center", gap: spacing.sm, alignItems: "center" },
  mutedText: { color: colors.onSurfaceSecondary, fontSize: 14, fontFamily: fonts.text },
  linkText: { color: colors.brandSecondary, fontSize: 14, fontFamily: fonts.textSemi },
}));
