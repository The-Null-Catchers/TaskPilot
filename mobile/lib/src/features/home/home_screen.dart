import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../auth/auth_controller.dart';
import 'home_controller.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(homeProvider);
    return Scaffold(appBar: AppBar(title: const Text('TaskPilot'), actions: [IconButton(onPressed:()=>ref.read(homeProvider.notifier).load(),icon:const Icon(Icons.refresh_rounded),tooltip:'Refresh'),IconButton(onPressed:()=>ref.read(authProvider.notifier).logout(),icon:const Icon(Icons.logout_rounded),tooltip:'Sign out')]), body: SafeArea(child: RefreshIndicator(onRefresh:()=>ref.read(homeProvider.notifier).load(),child:ListView(padding:const EdgeInsets.all(20),children:[
      if(state.offline) Container(margin:const EdgeInsets.only(bottom:16),padding:const EdgeInsets.all(12),decoration:BoxDecoration(color:Theme.of(context).colorScheme.secondaryContainer,borderRadius:BorderRadius.circular(14)),child:const Row(children:[Icon(Icons.cloud_off_rounded,size:18),SizedBox(width:8),Expanded(child:Text('Offline — showing cached workspace data.'))])),
      Text('Good to see you',style:Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight:FontWeight.w700)),const SizedBox(height:6),Text('Your workspaces and priorities, in one place.',style:Theme.of(context).textTheme.bodyLarge),const SizedBox(height:28),
      Row(mainAxisAlignment:MainAxisAlignment.spaceBetween,children:[Text('Workspaces',style:Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight:FontWeight.w700)),IconButton(onPressed:(){},icon:const Icon(Icons.add_rounded),tooltip:'Create workspace')]),
      if(state.loading) const Padding(padding:EdgeInsets.all(32),child:Center(child:CircularProgressIndicator())) else if(state.error!=null) Padding(padding:const EdgeInsets.symmetric(vertical:32),child:Text(state.error!,textAlign:TextAlign.center)) else ...state.workspaces.map((workspace)=>Card(elevation:0,child:ListTile(contentPadding:const EdgeInsets.symmetric(horizontal:18,vertical:10),leading:CircleAvatar(child:Text(workspace.name.substring(0,1).toUpperCase())),title:Text(workspace.name,style:const TextStyle(fontWeight:FontWeight.w600)),subtitle:const Text('Open projects and tasks'),trailing:const Icon(Icons.chevron_right_rounded),onTap:(){}))),
      const SizedBox(height:24),Text('Today',style:Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight:FontWeight.w700)),const SizedBox(height:12),Card(elevation:0,child:Padding(padding:const EdgeInsets.all(20),child:Row(children:[Icon(Icons.task_alt_rounded,color:Theme.of(context).colorScheme.primary),const SizedBox(width:14),const Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('My Tasks',style:TextStyle(fontWeight:FontWeight.w600)),SizedBox(height:4),Text('Task list and board sync are the next mobile slice.')]))]))),
    ]))));
  }
}
