import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'auth_controller.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});
  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final email = TextEditingController();
  final password = TextEditingController();
  final name = TextEditingController();
  bool register = false;

  @override
  void dispose() { email.dispose(); password.dispose(); name.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    return Scaffold(body: SafeArea(child: Center(child: SingleChildScrollView(padding: const EdgeInsets.all(24), child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 440), child: Card(elevation: 0, child: Padding(padding: const EdgeInsets.all(24), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [Container(width: 42,height:42,alignment:Alignment.center,decoration:BoxDecoration(color:Theme.of(context).colorScheme.primary,borderRadius:BorderRadius.circular(14)),child:const Text('T',style:TextStyle(color:Colors.white,fontWeight:FontWeight.bold,fontSize:20))),const SizedBox(width:12),const Text('TaskPilot',style:TextStyle(fontSize:22,fontWeight:FontWeight.w700))]),
      const SizedBox(height:32), Text(register?'Create your account':'Welcome back',style:Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight:FontWeight.w700)),const SizedBox(height:8),Text(register?'Your personal workspace is created automatically.':'Sign in to continue to your workspace.',style:Theme.of(context).textTheme.bodyMedium),const SizedBox(height:24),
      if(register)...[TextField(controller:name,textInputAction:TextInputAction.next,decoration:const InputDecoration(labelText:'Name')),const SizedBox(height:14)],
      TextField(controller:email,keyboardType:TextInputType.emailAddress,textInputAction:TextInputAction.next,decoration:const InputDecoration(labelText:'Email')),const SizedBox(height:14),TextField(controller:password,obscureText:true,onSubmitted:(_)=>submit(),decoration:const InputDecoration(labelText:'Password')),if(auth.error!=null)...[const SizedBox(height:12),Text(auth.error!,style:TextStyle(color:Theme.of(context).colorScheme.error))],const SizedBox(height:20),FilledButton(onPressed:auth.loading?null:submit,child:Padding(padding:const EdgeInsets.symmetric(vertical:13),child:Text(auth.loading?'Please wait…':register?'Create account':'Sign in'))),TextButton(onPressed:()=>setState(()=>register=!register),child:Text(register?'Already have an account? Sign in':'New to TaskPilot? Create an account'))
    ]))))))));
  }

  Future<void> submit() async {
    if (email.text.trim().isEmpty || password.text.length < 10 || (register && name.text.trim().length < 2)) return;
    if (register) { await ref.read(authProvider.notifier).register(name.text, email.text, password.text); } else { await ref.read(authProvider.notifier).login(email.text, password.text); }
  }
}
